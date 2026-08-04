"""Per-field confidence scoring after extraction + validation."""

from __future__ import annotations

import re
from typing import Any

from app.ocr.field_engine import normalize_money
from app.ocr.form_specs import get_field_specs
from app.ocr.types import DocumentSource, KiePair, OcrResult

_MONEY = re.compile(r"^(?:\$\s*)?-?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}$")
_SSN = re.compile(r"^(?:X{3}|x{3}|\*{3}|\d{3})-(?:X{2}|x{2}|\*{2}|\d{2})-\d{4}$")
_EIN = re.compile(r"^(?:\d{2}-\d{7}|\d{9})$")
_YEAR = re.compile(r"^20\d{2}$")

_SOURCE_BOOST: dict[DocumentSource, float] = {
    "digital_pdf": 0.15,
    "paddleocr_vl": 0.12,
    "pp_structure": 0.08,
    "paddle_ocr": 0.0,
}


def _shape_score(value_type: str, text: str) -> float:
    t = text.strip()
    if not t:
        return 0.0
    if value_type == "money":
        n = normalize_money(t)
        return 0.95 if n and _MONEY.match(n.replace(",", "")) else 0.4
    if value_type == "tin_ssn":
        return 0.95 if _SSN.match(t) else 0.35
    if value_type == "tin_ein":
        return 0.95 if _EIN.match(t) else 0.35
    if value_type == "year":
        return 0.95 if _YEAR.match(t) else 0.3
    if value_type == "address_block":
        return 0.85 if len(t) >= 12 else 0.5
    if value_type == "name_split":
        return 0.85 if re.search(r"[A-Za-z]{2,}", t) else 0.3
    return 0.75 if len(t) >= 2 else 0.4


def score_field_confidence(
    form_type: str,
    fields: dict[str, Any],
    ocr: OcrResult,
    kie_pairs: list[KiePair] | None = None,
) -> dict[str, float]:
    specs = {s.key: s for s in get_field_specs(form_type)}
    kie_by_key = {p.field_key: p for p in (kie_pairs or ocr.kie_pairs or [])}
    boost = _SOURCE_BOOST.get(ocr.source, 0.0)

    scores: dict[str, float] = {}
    for key, val in fields.items():
        if val is None or val == "":
            scores[key] = 0.0
            continue

        spec = specs.get(key)
        value_type = spec.value_type if spec else "raw"
        base = _shape_score(value_type, str(val))

        if key in kie_by_key:
            base = max(base, kie_by_key[key].confidence)

        # Token OCR confidence when available
        text_val = str(val).split()[0] if str(val) else ""
        token_confs = [
            t.confidence
            for page in ocr.pages
            for t in page.tokens
            if text_val and text_val in t.text and t.confidence < 1.0
        ]
        if token_confs:
            ocr_factor = sum(token_confs) / len(token_confs)
            base = base * 0.7 + ocr_factor * 0.3

        scores[key] = round(min(1.0, base + boost), 3)

    return scores
