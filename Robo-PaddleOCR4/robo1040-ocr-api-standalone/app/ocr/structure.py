"""PP-StructureV3 layout + OCR for scanned PDFs and image-heavy forms."""

from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from typing import Any

import numpy as np
from pdf2image import convert_from_bytes
from PIL import Image

from app.config import get_settings
from app.ocr.engine import _default_model_dir, _group_lines, _resize_for_ocr
from app.ocr.types import LayoutRegion, OcrPage, OcrResult, OcrToken


def _extract_payload(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw.get("res", raw)
    if hasattr(raw, "json") and callable(raw.json):
        data = raw.json()
        if isinstance(data, dict):
            return data.get("res", data)
    if hasattr(raw, "res"):
        return raw.res if isinstance(raw.res, dict) else {}
    return {}


def _regions_from_layout(payload: dict[str, Any]) -> list[LayoutRegion]:
    layout = payload.get("layout_det_res") or {}
    boxes = layout.get("boxes") or []
    regions: list[LayoutRegion] = []
    for box in boxes:
        if not isinstance(box, dict):
            continue
        coord = box.get("coordinate") or box.get("bbox")
        if not coord or len(coord) < 4:
            continue
        x1, y1, x2, y2 = coord[0], coord[1], coord[2], coord[3]
        regions.append(
            LayoutRegion(
                label=str(box.get("label") or "text"),
                left=int(min(x1, x2)),
                top=int(min(y1, y2)),
                right=int(max(x1, x2)),
                bottom=int(max(y1, y2)),
                score=float(box.get("score") or 1.0),
            )
        )
    return regions


def _tokens_from_ocr_payload(payload: dict[str, Any]) -> list[OcrToken]:
    ocr_res = payload.get("overall_ocr_res") or payload
    texts = ocr_res.get("rec_texts") or []
    scores = ocr_res.get("rec_scores")
    boxes = ocr_res.get("rec_boxes") or ocr_res.get("dt_polys")
    if scores is None:
        scores = [1.0] * len(texts)
    else:
        scores = list(np.asarray(scores).reshape(-1))
    tokens: list[OcrToken] = []
    if boxes is None:
        for text, score in zip(texts, scores):
            t = str(text).strip()
            if t:
                tokens.append(
                    OcrToken(text=t, confidence=float(score), left=0, top=0, right=0, bottom=0)
                )
        return tokens

    boxes_arr = np.asarray(boxes)
    for i, text in enumerate(texts):
        t = str(text).strip()
        if not t:
            continue
        box = boxes_arr[i] if i < len(boxes_arr) else None
        if box is None:
            left = top = right = bottom = 0
        else:
            flat = np.asarray(box).reshape(-1)
            if flat.size >= 4:
                xs = flat[0::2]
                ys = flat[1::2]
                left, right = int(xs.min()), int(xs.max())
                top, bottom = int(ys.min()), int(ys.max())
            else:
                left = top = right = bottom = 0
        tokens.append(
            OcrToken(
                text=t,
                confidence=float(scores[i]) if i < len(scores) else 1.0,
                left=left,
                top=top,
                right=right,
                bottom=bottom,
            )
        )
    return tokens


@lru_cache(maxsize=1)
def get_structure_pipeline():
    from paddleocr import PPStructureV3

    settings = get_settings()
    det_dir = _default_model_dir("PP-OCRv5_mobile_det")
    rec_dir = _default_model_dir("PP-OCRv5_mobile_rec")

    kwargs: dict[str, Any] = {
        "lang": "en",
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
        "use_formula_recognition": False,
        "use_seal_recognition": False,
        "use_table_recognition": False,
        "use_chart_recognition": False,
        "text_detection_model_name": "PP-OCRv5_mobile_det",
        "text_recognition_model_name": "PP-OCRv5_mobile_rec",
    }
    if det_dir:
        kwargs["text_detection_model_dir"] = det_dir
    if rec_dir:
        kwargs["text_recognition_model_dir"] = rec_dir
    if settings.pp_structure_config:
        kwargs["paddlex_config"] = settings.pp_structure_config
    return PPStructureV3(**kwargs)


def _structure_image(image: Image.Image) -> tuple[str, list[str], list[OcrToken], list[LayoutRegion]]:
    settings = get_settings()
    image = _resize_for_ocr(image, settings.ocr_max_side_px)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    # Preprocess image for better OCR accuracy (binarize, denoise, enhance)
    if settings.use_image_preprocessing:
        from app.ocr.preprocess import smart_preprocess
        image = smart_preprocess(image)

    pipeline = get_structure_pipeline()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        path = tmp.name
        image.save(path, format="PNG")
    try:
        outputs = pipeline.predict(input=path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    tokens: list[OcrToken] = []
    regions: list[LayoutRegion] = []
    if outputs:
        payload = _extract_payload(outputs[0])
        tokens = _tokens_from_ocr_payload(payload)
        regions = _regions_from_layout(payload)

    lines = _group_lines(tokens)
    text = "\n".join(lines)
    return text, lines, tokens, regions


def warmup_structure() -> None:
    """No-op: structure loads lazily on first scanned PDF (avoids startup CPU spike)."""
    return


def structure_models_cached() -> bool:
    """Lightweight check — do not load the full pipeline for /health."""
    from pathlib import Path

    root = Path.home() / ".paddlex" / "official_models"
    for name in ("PP-DocLayout_plus-L", "PP-DocLayout-L", "PP-DocLayout"):
        path = root / name
        if (path / "inference.yml").exists() or (path / "inference.json").exists():
            return True
    return False


def run_structure(
    pdf_bytes: bytes,
    left_half_only: bool = False,
    max_pages: int | None = None,
) -> OcrResult:
    settings = get_settings()
    last_page = max_pages if max_pages is not None else settings.max_pages
    images = convert_from_bytes(
        pdf_bytes,
        dpi=settings.ocr_dpi,
        fmt="png",
        first_page=1,
        last_page=last_page,
    )
    pages: list[OcrPage] = []
    for idx, image in enumerate(images, start=1):
        if left_half_only:
            image = image.crop((0, 0, image.width // 2, image.height))
        text, lines, tokens, regions = _structure_image(image)
        pages.append(
            OcrPage(
                page_number=idx,
                text=text,
                lines=lines,
                tokens=tokens,
                width=image.width,
                height=image.height,
                layout_regions=regions,
            )
        )
    return OcrResult(pages=pages, source="pp_structure")
