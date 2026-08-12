"""Multi-layout 1099-INT via spatial engine (no issuer logic in app code)."""

from pathlib import Path

from app.ocr.extractors.form_1099_int import extract_1099_int
from tests.test_all_identity import AMEX_INT, GOLDMAN_INT

FIXTURES = Path(__file__).parent / "fixtures"


def test_ally_combined_statement_fixture():
    f = extract_1099_int((FIXTURES / "1099_int_ally.txt").read_text(encoding="utf-8"))
    assert "BANK" in (f["PAYER'S name, address, and telephone"] or "").upper()
    assert "HORSHAM" in (f["PAYER'S name, address, and telephone"] or "")
    assert "MICHELLE" in (f["Recipient's Name"] or "")
    assert "RODRIGUEZ" in (f["Recipient's Name"] or "")
    assert "ROYAL COLONY" in (f["Recipient's Street Address (including apt. no.)"] or "")
    assert "JOHNS ISLAND" in (f["Recipient's city, state, country and Zip code"] or "")
    assert f["Recipient's TIN"] == "XXX-XX-4300"
    assert f["Payer's TIN"] == "20-1001796"
    assert f["1 Interest Income"] == "3909.17"
    assert f["Account Number"] == "2211545799"


def test_amex_irs_and_goldman_layouts():
    a = extract_1099_int(AMEX_INT)
    assert "NATIONAL BANK" in (a["PAYER'S name, address, and telephone"] or "").upper() or "EXPRESS" in (
        a["PAYER'S name, address, and telephone"] or ""
    ).upper()
    assert "TIMMERMAN" in (a["Recipient's Name"] or "")
    assert "GATE POST" in (a["Recipient's Street Address (including apt. no.)"] or "")
    assert a["1 Interest Income"] == "8986.68"

    g = extract_1099_int(GOLDMAN_INT)
    assert "Bank" in (g["PAYER'S name, address, and telephone"] or "") or "BANK" in (
        g["PAYER'S name, address, and telephone"] or ""
    ).upper()
    assert "Harmon" in (g["Recipient's Name"] or "")
    assert "372 Evian" in (g["Recipient's Street Address (including apt. no.)"] or "")
    assert g["1 Interest Income"] == "2653.39"


def test_amex_ocr_fixture_file():
    f = extract_1099_int((FIXTURES / "1099_int.txt").read_text(encoding="utf-8"))
    assert "EXPRESS" in (f["PAYER'S name, address, and telephone"] or "").upper() or "BANK" in (
        f["PAYER'S name, address, and telephone"] or ""
    ).upper()
    assert "TIMMERMAN" in (f["Recipient's Name"] or "")
    assert f["1 Interest Income"] == "8986.68"
    assert f["Account Number"] == "XXXXXX6333"


def test_first_citizens_bank_letter_layout():
    f = extract_1099_int((FIXTURES / "1099_int_first_citizens.txt").read_text(encoding="utf-8"))
    assert "FIRST-CITIZENS" in (f["PAYER'S name, address, and telephone"] or "").upper()
    assert "RALEIGH" in (f["PAYER'S name, address, and telephone"] or "")
    assert f["Payer's TIN"] == "56-0223230"
    assert "VICTORIA" in (f["Recipient's Name"] or "")
    assert "LOBECK" in (f["Recipient's Name"] or "")
    assert "BL0CKADE" in (f["Recipient's Street Address (including apt. no.)"] or "").upper() or "BLOCKADE" in (
        f["Recipient's Street Address (including apt. no.)"] or ""
    ).upper()
    assert "SUMMERVILLE" in (f["Recipient's city, state, country and Zip code"] or "").upper() or "SUMMERV" in (
        f["Recipient's city, state, country and Zip code"] or ""
    ).upper()
    assert f["Recipient's TIN"] == "XXX-XX-4453"
    assert f["Account Number"] == "00029267"
    assert f["1 Interest Income"] == "11.18"
    assert "IRS" not in (f["Recipient's Name"] or "").upper()
    assert "required" not in (f["Recipient's Name"] or "").lower()
