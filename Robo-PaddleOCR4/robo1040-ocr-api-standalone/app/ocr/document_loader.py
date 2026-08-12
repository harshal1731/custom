"""Unified document loader: PyMuPDF → PaddleOCR-VL → PP-StructureV3 → PaddleOCR.

Includes digital PDF quality gate: if embedded text is garbled (spaced
characters), automatically falls back to image-based VL/OCR with preprocessing.
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.ocr.digital_pdf import (
    extract_digital_pdf,
    is_blank_form_shell,
    is_digital_pdf,
    text_quality_score,
)
from app.ocr.engine import run_ocr
from app.ocr.kie_engine import run_kie
from app.ocr.paddleocr_vl import paddleocr_vl_available, run_paddleocr_vl
from app.ocr.structure import run_structure
from app.ocr.types import DocumentLoadResult, DocumentSource

logger = logging.getLogger(__name__)


def load_document(
    pdf_bytes: bytes,
    max_pages: int | None = None,
    left_half_only: bool = False,
    form_type: str | None = None,
) -> DocumentLoadResult:
    """Load PDF with best available path for accuracy and speed."""
    settings = get_settings()
    pages = max_pages if max_pages is not None else settings.single_form_max_pages
    source: DocumentSource = "paddle_ocr"
    is_digital = False
    ocr = None

    if settings.use_digital_pdf and is_digital_pdf(
        pdf_bytes, min_chars=settings.digital_pdf_min_chars, max_pages=pages
    ):
        quality = text_quality_score(pdf_bytes, max_pages=pages)
        blank_shell = is_blank_form_shell(pdf_bytes, max_pages=pages)
        if blank_shell:
            logger.info(
                "Digital PDF looks like an unfilled form shell (no money amounts) — "
                "falling back to VL/OCR"
            )
        elif quality <= settings.digital_pdf_quality_threshold:
            ocr = extract_digital_pdf(pdf_bytes, max_pages=pages)
            source = "digital_pdf"
            is_digital = True
        else:
            logger.info(
                "Digital PDF text quality too low (%.1f%% single-char words) — "
                "falling back to VL/OCR",
                quality * 100,
            )

    if ocr is None and settings.use_paddleocr_vl and paddleocr_vl_available():
        try:
            ocr = run_paddleocr_vl(pdf_bytes, left_half_only=left_half_only, max_pages=pages)
            source = "paddleocr_vl"
            logger.info("Loaded document via PaddleOCR-VL (%d pages)", ocr.page_count)
        except Exception as exc:
            logger.warning("PaddleOCR-VL failed, falling back: %s", exc)
            ocr = None

    if ocr is None:
        if settings.use_pp_structure:
            try:
                ocr = run_structure(pdf_bytes, left_half_only=left_half_only, max_pages=pages)
                source = "pp_structure"
            except Exception:
                ocr = run_ocr(pdf_bytes, left_half_only=left_half_only, max_pages=pages)
                source = "paddle_ocr"
        else:
            ocr = run_ocr(pdf_bytes, left_half_only=left_half_only, max_pages=pages)
            source = "paddle_ocr"

    ocr.source = source
    kie_pairs = run_kie(ocr, form_type) if form_type and settings.use_kie else []
    ocr.kie_pairs = kie_pairs

    return DocumentLoadResult(
        ocr=ocr,
        source=source,
        is_digital=is_digital,
        kie_pairs=kie_pairs,
        meta={"max_pages": pages, "left_half_only": left_half_only},
    )
