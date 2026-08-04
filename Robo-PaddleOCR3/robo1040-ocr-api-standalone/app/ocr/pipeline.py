from __future__ import annotations

from typing import Any, Callable

from app.config import get_settings
from app.ocr.classifier import Classification, classify_form
from app.ocr.confidence import score_field_confidence
from app.ocr.document_loader import load_document
from app.ocr.extractors.brokerage import extract_brokerage
from app.ocr.extractors.form_1099_div import extract_1099_div
from app.ocr.extractors.form_1099_int import extract_1099_int
from app.ocr.extractors.form_5498_sa import extract_5498_sa
from app.ocr.extractors.w2 import extract_w2
from app.ocr.kie_engine import enhance_with_spatial_engine, merge_kie_fields
from app.ocr.schema_extract import (
    merge_schema_fields,
    run_schema_extraction,
    schema_fields_to_kie_pairs,
)
from app.ocr.types import DocumentLoadResult, OcrResult
from app.ocr.validators import validate_fields

Extractor = Callable[[OcrResult | str], dict[str, Any]]

EXTRACTORS: dict[str, Extractor] = {
    "W-2": extract_w2,
    "1099-INT": extract_1099_int,
    "1099-DIV": extract_1099_div,
    "5498-SA": extract_5498_sa,
    "Consolidated Brokerage Statement": extract_brokerage,
}


def extract_fields(form_type: str, source: OcrResult | str) -> dict[str, Any]:
    extractor = EXTRACTORS.get(form_type)
    if extractor is None:
        text = source if isinstance(source, str) else source.full_text
        return {"raw_ocr_text": text[:4000]}
    return extractor(source)


def process_pdf(pdf_bytes: bytes) -> tuple[Classification, DocumentLoadResult, dict[str, Any], dict[str, float]]:
    settings = get_settings()

    doc = load_document(pdf_bytes, max_pages=settings.single_form_max_pages)
    classification = classify_form(doc.ocr.full_text)

    if classification.form_type == "Consolidated Brokerage Statement":
        doc = load_document(
            pdf_bytes,
            max_pages=settings.brokerage_max_pages,
            form_type=classification.form_type,
        )
    elif settings.use_kie and classification.form_type in EXTRACTORS:
        from app.ocr.kie_engine import run_kie

        doc.kie_pairs = run_kie(doc.ocr, classification.form_type)
        doc.ocr.kie_pairs = doc.kie_pairs

    # 1) Heuristic / spatial extractors
    fields = extract_fields(classification.form_type, doc.ocr)

    # 2) Spatial KIE pairs
    fields = merge_kie_fields(fields, doc.kie_pairs, classification.form_type)

    # 3) Schema-driven fill (rules + optional local LLM) — key path to 90%+
    schema_fields = run_schema_extraction(classification.form_type, doc.ocr)
    if schema_fields:
        fields = merge_schema_fields(fields, schema_fields, classification.form_type)
        method = "schema_llm" if settings.schema_llm_base_url else "schema"
        doc.kie_pairs = list(doc.kie_pairs) + schema_fields_to_kie_pairs(schema_fields, method=method)
        doc.ocr.kie_pairs = doc.kie_pairs

    # 4) Fill remaining address/role gaps via spatial engine
    fields = enhance_with_spatial_engine(doc.ocr, classification.form_type, fields)

    fields = validate_fields(classification.form_type, fields)
    field_confidence = score_field_confidence(
        classification.form_type, fields, doc.ocr, doc.kie_pairs
    )

    return classification, doc, fields, field_confidence
