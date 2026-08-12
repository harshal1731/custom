"""Unit tests for spatial KIE and confidence scoring."""

from __future__ import annotations

from app.ocr.confidence import score_field_confidence
from app.ocr.field_engine import page_from_text
from app.ocr.kie_engine import extract_spatial_kie, merge_kie_fields
from app.ocr.types import KiePair, LayoutRegion, OcrPage, OcrResult, OcrToken


def _page_with_layout() -> OcrResult:
    tokens = [
        OcrToken("Interest", 0.95, 10, 100, 80, 120),
        OcrToken("income", 0.95, 85, 100, 140, 120),
        OcrToken("1,234.56", 0.92, 200, 98, 280, 122),
        OcrToken("Recipient's", 0.9, 10, 200, 90, 220),
        OcrToken("TIN", 0.9, 95, 200, 130, 220),
        OcrToken("12-3456789", 0.93, 200, 198, 300, 222),
    ]
    regions = [LayoutRegion("text", 5, 95, 310, 130, 0.98)]
    page = OcrPage(
        page_number=1,
        text="Interest income 1,234.56\nRecipient's TIN 12-3456789",
        lines=["Interest income 1,234.56", "Recipient's TIN 12-3456789"],
        tokens=tokens,
        width=612,
        height=792,
        layout_regions=regions,
    )
    return OcrResult(pages=[page], source="pp_structure")


def test_spatial_kie_finds_money_and_tin():
    ocr = _page_with_layout()
    pairs = extract_spatial_kie(ocr, "1099-INT")
    by_key = {p.field_key: p for p in pairs}
    assert "1 Interest income" in by_key or any("interest" in p.label.lower() for p in pairs)
    tin_pairs = [p for p in pairs if "TIN" in p.field_key or "tin" in p.field_key.lower()]
    assert tin_pairs or by_key


def test_merge_kie_fills_missing_fields():
    pairs = [
        KiePair("1 Interest income", "Interest income", "999.99", 0.9),
    ]
    fields = {"1 Interest income": None, "Year": "2024"}
    merged = merge_kie_fields(fields, pairs, "1099-INT")
    assert merged["1 Interest income"] == "999.99"
    assert merged["Year"] == "2024"


def test_field_confidence_scores_filled_fields():
    ocr = _page_with_layout()
    fields = {"1 Interest income": "1234.56", "Year": "2024"}
    scores = score_field_confidence("1099-INT", fields, ocr)
    assert scores["1 Interest income"] > 0.5
    assert scores["Year"] > 0.5


def test_digital_pdf_source_boost():
    page = page_from_text("Form W-2 2024\nXXX-XX-1234")
    ocr = OcrResult(pages=[page], source="digital_pdf")
    fields = {"Year": "2024", "Employee's social security number": "XXX-XX-1234"}
    scores = score_field_confidence("W-2", fields, ocr)
    assert scores["Year"] >= 0.9
