"""Tests for PyMuPDF digital PDF detection and extraction."""

from __future__ import annotations

import pytest

fitz = pytest.importorskip("fitz")

from app.ocr.digital_pdf import extract_digital_pdf, is_digital_pdf


def _make_text_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    return doc.tobytes()


def test_is_digital_pdf_detects_text_layer():
    sample = "Form W-2 Wage and Tax Statement 2024\n" * 20
    pdf = _make_text_pdf(sample)
    assert is_digital_pdf(pdf, min_chars=200)


def test_extract_digital_pdf_returns_tokens():
    sample = "Employee social security number XXX-XX-1234 Wages 2800.00"
    pdf = _make_text_pdf(sample)
    result = extract_digital_pdf(pdf, max_pages=1)
    assert result.source == "digital_pdf"
    assert result.page_count == 1
    assert "2800.00" in result.full_text or "2800" in result.full_text
    assert len(result.pages[0].tokens) >= 3
