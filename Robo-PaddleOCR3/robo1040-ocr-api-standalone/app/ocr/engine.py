from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import numpy as np
from pdf2image import convert_from_bytes
from PIL import Image

from app.config import get_settings
from app.ocr.types import OcrPage, OcrResult, OcrToken

__all__ = [
    "OcrToken",
    "OcrPage",
    "OcrResult",
    "run_ocr",
    "filter_tokens_left_half",
    "text_from_tokens",
    "normalize_money",
    "find_ssn",
    "find_ein",
    "find_year",
    "find_money_after_label",
    "find_value_near_box",
]


def _default_model_dir(name: str) -> str | None:
    """Prefer baked/local model dirs so startup does not depend on hoster checks."""
    import os
    from pathlib import Path

    here = Path(__file__).resolve()
    package_root = here.parents[2]  # .../app/ocr/engine.py -> package root
    candidates = [
        Path(os.environ["PADDLE_MODEL_ROOT"]) / name
        if os.environ.get("PADDLE_MODEL_ROOT")
        else None,
        package_root / "models" / name,
        Path.cwd() / "models" / name,
        Path("/root/.paddlex/official_models") / name,
        Path.home() / ".paddlex" / "official_models" / name,
    ]
    for path in candidates:
        if path is None:
            continue
        if (path / "inference.yml").exists() or (path / "inference.json").exists():
            return str(path)
    return None


@lru_cache(maxsize=1)
def get_ocr():
    from paddleocr import PaddleOCR

    det_dir = _default_model_dir("PP-OCRv5_mobile_det")
    rec_dir = _default_model_dir("PP-OCRv5_mobile_rec")

    # Mobile models stay free/CPU-friendly and usually finish under 15s/page.
    kwargs = {
        "text_detection_model_name": "PP-OCRv5_mobile_det",
        "text_recognition_model_name": "PP-OCRv5_mobile_rec",
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
    }
    if det_dir:
        kwargs["text_detection_model_dir"] = det_dir
    if rec_dir:
        kwargs["text_recognition_model_dir"] = rec_dir
    return PaddleOCR(**kwargs)


def _extract_predict_payload(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw.get("res", raw)
    # PaddleOCR 3.x result objects often expose .json / attributes
    if hasattr(raw, "json") and callable(raw.json):
        data = raw.json()
        if isinstance(data, dict):
            return data.get("res", data)
    if hasattr(raw, "res"):
        return raw.res if isinstance(raw.res, dict) else {}
    texts = getattr(raw, "rec_texts", None)
    scores = getattr(raw, "rec_scores", None)
    boxes = getattr(raw, "rec_boxes", None)
    if texts is not None:
        return {"rec_texts": texts, "rec_scores": scores, "rec_boxes": boxes}
    return {}


def _tokens_from_payload(payload: dict[str, Any]) -> list[OcrToken]:
    texts = payload.get("rec_texts") or []
    scores = payload.get("rec_scores")
    boxes = payload.get("rec_boxes")
    if scores is None:
        scores = [1.0] * len(texts)
    else:
        scores = list(np.asarray(scores).reshape(-1))
    tokens: list[OcrToken] = []
    if boxes is None:
        for text, score in zip(texts, scores):
            if not str(text).strip():
                continue
            tokens.append(
                OcrToken(
                    text=str(text).strip(),
                    confidence=float(score),
                    left=0,
                    top=0,
                    right=0,
                    bottom=0,
                )
            )
        return tokens

    boxes_arr = np.asarray(boxes)
    for i, text in enumerate(texts):
        t = str(text).strip()
        if not t:
            continue
        box = boxes_arr[i]
        # box can be [x1,y1,x2,y2] or polygon
        flat = np.asarray(box).reshape(-1)
        if flat.size >= 4 and flat.size % 2 == 0:
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


def _group_lines(tokens: list[OcrToken], y_tol: int = 18) -> list[str]:
    if not tokens:
        return []
    ordered = sorted(tokens, key=lambda t: (t.top, t.left))
    lines: list[list[OcrToken]] = []
    current: list[OcrToken] = []
    current_y: float | None = None
    for tok in ordered:
        if current_y is None or abs(tok.cy - current_y) <= y_tol:
            current.append(tok)
            current_y = tok.cy if current_y is None else (current_y * 0.7 + tok.cy * 0.3)
        else:
            lines.append(sorted(current, key=lambda t: t.left))
            current = [tok]
            current_y = tok.cy
    if current:
        lines.append(sorted(current, key=lambda t: t.left))
    return [" ".join(t.text for t in line) for line in lines]


def _resize_for_ocr(image: Image.Image, max_side: int) -> Image.Image:
    w, h = image.size
    longest = max(w, h)
    if longest <= max_side:
        return image
    scale = max_side / longest
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def warmup_ocr() -> None:
    """Load models and run one tiny predict so first request stays under SLA."""
    from PIL import ImageDraw

    ocr = get_ocr()
    img = Image.new("RGB", (640, 480), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), "W-2 2024 Interest income $0.00", fill=(0, 0, 0))
    arr = np.array(img)
    ocr.predict(arr)


def _ocr_image(image: Image.Image) -> tuple[str, list[str], list[OcrToken]]:
    settings = get_settings()
    image = _resize_for_ocr(image, settings.ocr_max_side_px)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    # Preprocess image for better OCR accuracy (binarize, denoise, enhance)
    if settings.use_image_preprocessing:
        from app.ocr.preprocess import smart_preprocess
        image = smart_preprocess(image)

    arr = np.array(image)
    ocr = get_ocr()
    outputs = ocr.predict(arr)
    tokens: list[OcrToken] = []
    if outputs:
        payload = _extract_predict_payload(outputs[0])
        tokens = _tokens_from_payload(payload)
    lines = _group_lines(tokens)
    text = "\n".join(lines)
    return text, lines, tokens


def run_ocr(
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
        text, lines, tokens = _ocr_image(image)
        pages.append(
            OcrPage(
                page_number=idx,
                text=text,
                lines=lines,
                tokens=tokens,
                width=image.width,
                height=image.height,
            )
        )
    return OcrResult(pages=pages)


def filter_tokens_left_half(page: OcrPage) -> list[OcrToken]:
    if page.width <= 0:
        return page.tokens
    mid = page.width / 2
    return [t for t in page.tokens if t.cx <= mid]


def text_from_tokens(tokens: list[OcrToken]) -> str:
    return "\n".join(_group_lines(tokens))


_MONEY = r"(?:\$\s*)?-?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}"


def normalize_money(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().replace("$", "").replace(",", "").replace(" ", "")
    cleaned = cleaned.replace("O", "0").replace("o", "0")
    if not cleaned or cleaned in {".", "-"}:
        return None
    if re.fullmatch(r"-?\d+(\.\d{1,2})?", cleaned):
        return cleaned
    return value.strip()


def find_ssn(text: str) -> str | None:
    m = re.search(r"\b(\d{3}-\d{2}-\d{4})\b", text)
    if m:
        return m.group(1)
    m = re.search(r"\b((?:X{3}|x{3}|\d{3})-(?:X{2}|x{2}|\d{2})-\d{4})\b", text)
    return m.group(1) if m else None


def find_ein(text: str) -> str | None:
    m = re.search(r"\b(\d{2}-\d{7})\b", text)
    return m.group(1) if m else None


def find_year(text: str) -> str | None:
    m = re.search(r"\b(20\d{2})\b", text)
    return m.group(1) if m else None


def find_money_after_label(text: str, labels: list[str]) -> str | None:
    for label in labels:
        pattern = rf"{re.escape(label)}.{{0,80}}?({_MONEY})"
        m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return normalize_money(m.group(1))
    return None


def find_value_near_box(text: str, box: str) -> str | None:
    pattern = rf"(?:^|[\s|]){re.escape(box)}(?:\s|[.|:)>-])+({_MONEY})"
    m = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if m:
        return normalize_money(m.group(1))
    return None
