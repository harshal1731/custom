"""Print exact key-field accuracy scores for fixtures + multi-layout INT."""
from __future__ import annotations

from pathlib import Path

from app.ocr.extractors.brokerage import extract_brokerage
from app.ocr.extractors.form_1099_div import extract_1099_div
from app.ocr.extractors.form_1099_int import extract_1099_int
from app.ocr.extractors.form_5498_sa import extract_5498_sa
from app.ocr.extractors.w2 import extract_w2
from tests.test_all_identity import AMEX_INT, GOLDMAN_INT

FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures"


def score(fields: dict, expected: dict[str, str]) -> tuple[float, list[str]]:
    misses = []
    hits = 0
    for key, needle in expected.items():
        val = str(fields.get(key) or "")
        if needle.lower() in val.lower():
            hits += 1
        else:
            misses.append(f"{key}: got={val!r} want~={needle!r}")
    return hits / len(expected), misses


CASES = [
    (
        "W-2",
        extract_w2,
        (FIXTURES / "w2.txt").read_text(encoding="utf-8"),
        {
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
            "Employee's address and ZIP code": "31058",
            "16 State wages, tips, etc.": "2800.00",
            "17 State income tax": "113.68",
        },
    ),
    (
        "1099-INT Amex OCR",
        extract_1099_int,
        (FIXTURES / "1099_int.txt").read_text(encoding="utf-8"),
        {
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
        },
    ),
    (
        "1099-INT Ally OCR",
        extract_1099_int,
        (FIXTURES / "1099_int_ally.txt").read_text(encoding="utf-8"),
        {
            "Year": "2024",
            "Recipient's Name": "MICHELLE",
            "Recipient's Street Address (including apt. no.)": "ROYAL COLONY",
            "Recipient's city, state, country and Zip code": "JOHNS ISLAND",
            "PAYER'S name, address, and telephone": "BANK",
            "Payer's TIN": "20-1001796",
            "Recipient's TIN": "XXX-XX-4300",
            "1 Interest Income": "3909.17",
            "Account Number": "2211545799",
            "2 Early withdrawal penalty": "0.00",
        },
    ),
    (
        "1099-INT Goldman layout",
        extract_1099_int,
        GOLDMAN_INT,
        {
            "Recipient's Name": "Andrew Harmon",
            "Recipient's Street Address (including apt. no.)": "372 Evian",
            "PAYER'S name, address, and telephone": "Bank",
            "Account Number": "910190526036",
            "1 Interest Income": "2653.39",
            "Payer's TIN": "13-3571598",
        },
    ),
    (
        "1099-DIV",
        extract_1099_div,
        (FIXTURES / "1099_div.txt").read_text(encoding="utf-8"),
        {
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
        },
    ),
    (
        "5498-SA",
        extract_5498_sa,
        (FIXTURES / "5498_sa.txt").read_text(encoding="utf-8"),
        {
            "Year": "2024",
            "TRUSTEE'S or ISSUER'S name, street address, city, state, ZIP": "Bank",
            "PARTICIPANT'S name": "Daniel Sommer",
            "Street address (including apt. no.)": "CORN PLANTERS",
            "City, state, and ZIP": "DANIEL ISLAND",
            "Account number": "411464244",
            "2 Total contributions": "0.00",
            "5 FMV of HSA, Archer MSA, or MA MSA": "888.68",
            "6 HSA": "Yes",
        },
    ),
    (
        "Brokerage",
        extract_brokerage,
        (FIXTURES / "brokerage.txt").read_text(encoding="utf-8"),
        {
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
        },
    ),
]


def main() -> None:
    for name, fn, text, expected in CASES:
        fields = fn(text)
        pct, misses = score(fields, expected)
        status = "PASS>=90%" if pct >= 0.90 else "BELOW 90%"
        print(f"{name}: {pct*100:.1f}% ({int(pct*len(expected))}/{len(expected)}) {status}")
        for m in misses:
            print(f"  MISS {m}")


if __name__ == "__main__":
    main()
