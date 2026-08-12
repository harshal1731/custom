"""FieldSpec registry per form type (IRS labels only — no issuer hardcodes)."""

from __future__ import annotations

from app.ocr.extractors.brokerage import _specs as brokerage_specs
from app.ocr.extractors.form_1099_div import _specs as div_specs
from app.ocr.extractors.form_1099_int import _specs as int_specs
from app.ocr.extractors.form_5498_sa import _specs as sa_specs
from app.ocr.extractors.w2 import _specs as w2_specs
from app.ocr.field_engine import FieldSpec

FORM_SPECS: dict[str, list[FieldSpec]] = {
    "W-2": w2_specs(),
    "1099-INT": int_specs(),
    "1099-DIV": div_specs(),
    "5498-SA": sa_specs(),
    "Consolidated Brokerage Statement": brokerage_specs(),
}


def get_field_specs(form_type: str) -> list[FieldSpec]:
    factory = {
        "W-2": w2_specs,
        "1099-INT": int_specs,
        "1099-DIV": div_specs,
        "5498-SA": sa_specs,
        "Consolidated Brokerage Statement": brokerage_specs,
    }.get(form_type)
    return factory() if factory else []
