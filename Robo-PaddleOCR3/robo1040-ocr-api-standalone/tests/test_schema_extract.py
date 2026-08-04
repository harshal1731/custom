"""Tests for schema-driven extraction (offline, no VL models required)."""

from __future__ import annotations

from app.ocr.schema_extract import (
    extract_schema_rules,
    merge_schema_fields,
    schema_for_form,
)
from app.ocr.types import OcrPage, OcrResult


SAMPLE_INT = """
Form 1099-INT 2024
PAYER'S TIN 12-3456789
RECIPIENT'S TIN XXX-XX-1234
Recipient's Name JANE DOE
Interest income 1,234.56
Account number ABCD1234
"""


def test_schema_for_form_has_interest_field():
    schema = schema_for_form("1099-INT")
    assert "1 Interest Income" in schema["properties"]
    assert schema["properties"]["1 Interest Income"]["value_type"] == "money"


def test_extract_schema_rules_fills_money_and_tins():
    fields = extract_schema_rules("1099-INT", SAMPLE_INT)
    assert fields.get("Year") == "2024"
    assert fields.get("Payer's TIN") == "12-3456789"
    assert fields.get("1 Interest Income") == "1234.56"


def test_merge_schema_fills_missing_only():
    base = {"Year": "2024", "1 Interest Income": None}
    schema = {"1 Interest Income": "99.00", "Year": "2023"}
    merged = merge_schema_fields(base, schema, "1099-INT")
    assert merged["1 Interest Income"] == "99.00"
    assert merged["Year"] == "2024"  # existing kept


def test_pipeline_schema_path_with_markdown_ocr():
    from app.ocr.schema_extract import run_schema_extraction

    page = OcrPage(page_number=1, text=SAMPLE_INT, lines=SAMPLE_INT.splitlines())
    ocr = OcrResult(pages=[page], source="paddleocr_vl", markdown=SAMPLE_INT)
    out = run_schema_extraction("1099-INT", ocr)
    assert out.get("1 Interest Income") == "1234.56"
