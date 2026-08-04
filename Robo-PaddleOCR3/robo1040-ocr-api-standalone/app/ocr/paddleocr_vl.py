"""PaddleOCR-VL document parsing (self-hosted VLM, 0.9B).

Produces high-quality markdown/text for schema extraction. Falls back gracefully
when PaddleOCRVL is unavailable (older paddleocr) or models are not downloaded.
"""

from __future__ import annotations

import logging
import os
import tempfile
from functools import lru_cache
from typing import Any

from pdf2image import convert_from_bytes
from PIL import Image

from app.config import get_settings
from app.ocr.engine import _group_lines, _resize_for_ocr
from app.ocr.types import LayoutRegion, OcrPage, OcrResult, OcrToken

logger = logging.getLogger(__name__)


def paddleocr_vl_available() -> bool:
    try:
        from paddleocr import PaddleOCRVL  # noqa: F401

        return True
    except Exception:
        return False


@lru_cache(maxsize=1)
def get_vl_pipeline():
    from paddleocr import PaddleOCRVL

    settings = get_settings()
    kwargs: dict[str, Any] = {
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_chart_recognition": False,
        "use_seal_recognition": False,
    }
    if settings.paddleocr_vl_device:
        kwargs["device"] = settings.paddleocr_vl_device
    if settings.paddleocr_vl_model_dir:
        kwargs["vl_rec_model_dir"] = settings.paddleocr_vl_model_dir
    if settings.paddleocr_vl_model_name:
        kwargs["vl_rec_model_name"] = settings.paddleocr_vl_model_name
    if settings.paddleocr_vl_backend:
        kwargs["vl_rec_backend"] = settings.paddleocr_vl_backend
    if settings.paddleocr_vl_server_url:
        kwargs["vl_rec_server_url"] = settings.paddleocr_vl_server_url

    return PaddleOCRVL(**kwargs)


def _extract_payload(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw.get("res", raw)
    if hasattr(raw, "json") and callable(raw.json):
        data = raw.json()
        if isinstance(data, dict):
            return data.get("res", data)
    if hasattr(raw, "res") and isinstance(raw.res, dict):
        return raw.res
    # Common VL result attributes
    out: dict[str, Any] = {}
    for attr in ("markdown", "parsing_res_list", "layout_det_res", "overall_ocr_res"):
        if hasattr(raw, attr):
            out[attr] = getattr(raw, attr)
    return out


def _markdown_from_payload(payload: dict[str, Any], raw: Any) -> str:
    md = payload.get("markdown")
    if isinstance(md, dict):
        text = md.get("markdown_texts") or md.get("text") or ""
        if isinstance(text, list):
            return "\n\n".join(str(t) for t in text if t)
        return str(text or "")
    if isinstance(md, str) and md.strip():
        return md
    if hasattr(raw, "markdown"):
        m = raw.markdown
        if isinstance(m, dict):
            return str(m.get("markdown_texts") or m.get("text") or "")
        if isinstance(m, str):
            return m
    # Fallback: join parsing blocks
    blocks = payload.get("parsing_res_list") or []
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, dict):
            content = block.get("block_content") or block.get("content") or ""
            if content:
                parts.append(str(content))
        elif hasattr(block, "block_content"):
            parts.append(str(block.block_content))
    return "\n".join(parts)


def _tokens_from_payload(payload: dict[str, Any]) -> list[OcrToken]:
    ocr_res = payload.get("overall_ocr_res") or {}
    texts = ocr_res.get("rec_texts") or []
    scores = ocr_res.get("rec_scores") or [1.0] * len(texts)
    boxes = ocr_res.get("rec_boxes") or ocr_res.get("dt_polys")
    tokens: list[OcrToken] = []
    if not texts:
        return tokens
    if boxes is None:
        for text, score in zip(texts, scores):
            t = str(text).strip()
            if t:
                tokens.append(OcrToken(t, float(score), 0, 0, 0, 0))
        return tokens

    import numpy as np

    boxes_arr = np.asarray(boxes)
    for i, text in enumerate(texts):
        t = str(text).strip()
        if not t:
            continue
        flat = np.asarray(boxes_arr[i]).reshape(-1) if i < len(boxes_arr) else None
        if flat is not None and flat.size >= 4:
            xs, ys = flat[0::2], flat[1::2]
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


def _regions_from_payload(payload: dict[str, Any]) -> list[LayoutRegion]:
    layout = payload.get("layout_det_res") or {}
    boxes = layout.get("boxes") or []
    regions: list[LayoutRegion] = []
    for box in boxes:
        if not isinstance(box, dict):
            continue
        coord = box.get("coordinate") or box.get("bbox")
        if not coord or len(coord) < 4:
            continue
        x1, y1, x2, y2 = coord[:4]
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


def _vl_image(image: Image.Image) -> tuple[str, list[str], list[OcrToken], list[LayoutRegion], str]:
    settings = get_settings()
    image = _resize_for_ocr(image, settings.ocr_max_side_px)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    pipeline = get_vl_pipeline()
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
    markdown = ""
    if outputs:
        raw = outputs[0]
        payload = _extract_payload(raw)
        markdown = _markdown_from_payload(payload, raw)
        tokens = _tokens_from_payload(payload)
        regions = _regions_from_payload(payload)

    if tokens:
        lines = _group_lines(tokens)
        text = "\n".join(lines)
    elif markdown:
        lines = [ln for ln in markdown.splitlines() if ln.strip()]
        text = "\n".join(lines)
        # Synthetic left-to-right tokens so downstream spatial KIE still works
        y = 0
        for line in lines:
            for i, word in enumerate(line.split()):
                tokens.append(OcrToken(word, 0.95, i * 40, y, i * 40 + 36, y + 14))
            y += 18
    else:
        lines, text = [], ""

    return text, lines, tokens, regions, markdown


def run_paddleocr_vl(
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
    markdown_parts: list[str] = []
    for idx, image in enumerate(images, start=1):
        if left_half_only:
            image = image.crop((0, 0, image.width // 2, image.height))
        text, lines, tokens, regions, markdown = _vl_image(image)
        if markdown:
            markdown_parts.append(markdown)
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
    result = OcrResult(pages=pages, source="paddleocr_vl", markdown="\n\n".join(markdown_parts))
    return result


def vl_models_cached() -> bool:
    """Lightweight presence check for VL recognition model files."""
    from pathlib import Path

    root = Path.home() / ".paddlex" / "official_models"
    for name in (
        "PaddleOCR-VL",
        "PaddleOCR-VL-0.9B",
        "PaddleOCR-VL-1.5",
        "PaddleOCR-VL-1.6",
    ):
        path = root / name
        if path.exists() and any(path.iterdir()):
            return True
    return False
