"""Local fixture accuracy tests — no Docker / OCR required."""

from __future__ import annotations

from pathlib import Path

from app.ocr.classifier import classify_form
from app.ocr.extractors.brokerage import extract_brokerage
from app.ocr.extractors.form_1099_div import extract_1099_div
from app.ocr.extractors.form_1099_int import extract_1099_int
from app.ocr.extractors.form_5498_sa import extract_5498_sa
from app.ocr.extractors.w2 import extract_w2
from tests.test_all_identity import AMEX_INT, GOLDMAN_INT

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8", errors="ignore")


def _score(fields: dict, expected: dict[str, str]) -> float:
    hits = 0
    for key, needle in expected.items():
        val = fields.get(key) or ""
        if needle.lower() in str(val).lower():
            hits += 1
    return hits / len(expected) if expected else 0.0


def test_classify_fixtures():
    assert classify_form(_load("w2.txt")).form_type == "W-2"
    assert classify_form(_load("1099_int.txt")).form_type == "1099-INT"
    assert classify_form(_load("1099_div.txt")).form_type == "1099-DIV"
    assert classify_form(_load("5498_sa.txt")).form_type == "5498-SA"
    assert classify_form(_load("brokerage.txt")).form_type == "Consolidated Brokerage Statement"


def test_w2_fixture_accuracy():
    f = extract_w2(_load("w2.txt"))
    expected = {
        "Year": "2024",
        "Employee's social security number": "XXX-XX-2930",
        "Employer identification number (EIN)": "57-1110444",
        "1 Wages, tips, other compensation": "2800.00",
        "2 Federal income tax withheld": "1365.22",
        "3 Social security wages": "2800.00",
        "4 Social security tax withheld": "173.60",
        "5 Medicare wages and tips": "2800.00",
        "6 Medicare tax withheld": "40.60",
        "Control number": "20230218-3",
        "Employee's first name and initial": "Thomas",
        "Last name": "Masi",
        "Employer's name, address, and ZIP code": "I INS U Inc",
        "Employee's address and ZIP code": "PO Box 31058",
        "16 State wages, tips, etc.": "2800.00",
        "17 State income tax": "113.68",
    }
    assert _score(f, expected) >= 0.90, f


def test_1099_int_fixture_and_layouts():
    f = extract_1099_int(_load("1099_int.txt"))
    expected = {
        "Year": "2024",
        "Payer's TIN": "11-2869526",
        "Recipient's TIN": "XXX-XX-4860",
        "Recipient's Name": "TIMMERMAN",
        "Recipient's Street Address (including apt. no.)": "GATE POST",
        "Recipient's city, state, country and Zip code": "MOUNT PLEASANT",
        "PAYER'S name, address, and telephone": "BANK",
        "Account Number": "XXXXXX6333",
        "1 Interest Income": "8986.68",
        "2 Early withdrawal penalty": "0.00",
    }
    assert _score(f, expected) >= 0.90, f

    g = extract_1099_int(GOLDMAN_INT)
    assert _score(
        g,
        {
            "Recipient's Name": "Andrew Harmon",
            "Recipient's Street Address (including apt. no.)": "372 Evian",
            "PAYER'S name, address, and telephone": "Bank",
            "Account Number": "910190526036",
            "1 Interest Income": "2653.39",
            "Payer's TIN": "13-3571598",
        },
    ) >= 0.90, g

    a = extract_1099_int(AMEX_INT)
    assert a["1 Interest Income"] == "8986.68"
    assert "TIMMERMAN" in (a["Recipient's Name"] or "")

    ally = extract_1099_int(_load("1099_int_ally.txt"))
    assert _score(
        ally,
        {
            "Recipient's Name": "MICHELLE",
            "Recipient's Street Address (including apt. no.)": "ROYAL COLONY",
            "1 Interest Income": "3909.17",
            "Payer's TIN": "20-1001796",
            "PAYER'S name, address, and telephone": "BANK",
        },
    ) >= 0.90, ally


def test_1099_div_fixture_accuracy():
    f = extract_1099_div(_load("1099_div.txt"))
    expected = {
        "Year": "2024",
        "Payer's TIN": "51-6516897",
        "Recipient's Name": "PERROTT",
        "Recipient's Street Address (including apt. no.)": "PRESIDENTIAL",
        "Recipient's city, state, country and Zip code": "HORSEHEADS",
        "PAYER'S name, address, and telephone": "COMPUTERSHARE",
        "Account Number": "C0042388017",
        "1a Total ordinary dividends": "342.66",
        "1b Qualified dividends": "342.66",
        "3 Nondividend distributions": "0.00",
        "4 Federal income tax withheld": "0.00",
    }
    assert _score(f, expected) >= 0.90, f


def test_5498_sa_fixture_accuracy():
    f = extract_5498_sa(_load("5498_sa.txt"))
    expected = {
        "Year": "2024",
        "TRUSTEE'S or ISSUER'S name, street address, city, state, ZIP": "Optum",
        "PARTICIPANT'S name": "Daniel Sommer",
        "Street address (including apt. no.)": "CORN PLANTERS",
        "City, state, and ZIP": "DANIEL ISLAND",
        "Account number": "411464244",
        "2 Total contributions": "0.00",
        "5 FMV of HSA, Archer MSA, or MA MSA": "888.68",
        "6 HSA": "Yes",
    }
    assert _score(f, expected) >= 0.90, f


def test_brokerage_fixture_accuracy():
    f = extract_brokerage(_load("brokerage.txt"))
    expected = {
        "Year": "2024",
        "Account Number": "6852-5051",
        "Recipient's Name": "CLIFTON",
        "Recipient's Street Address (including apt. no.)": "SOUTHWOLD",
        "Recipient City": "GOOSE CREEK",
        "Recipient State": "SC",
        "Payer Name": "CO",
        "1a Total ordinary dividends": "598.71",
        "1b Qualified dividends": "598.71",
        "2a Total capital gain distr.": "0.00",
    }
    assert _score(f, expected) >= 0.90, f


def test_no_hardcoded_cross_pollution():
    """Goldman layout must not invent Amex payer / Heath recipient."""
    f = extract_1099_int(GOLDMAN_INT)
    blob = " ".join(str(v) for v in f.values() if v)
    assert "AMERICAN EXPRESS" not in blob.upper()
    assert "HEATH" not in blob.upper()
    assert "TIMMERMAN" not in blob.upper()
