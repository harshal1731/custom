"""Live Docker accuracy on one PDF per form type (key fields)."""
from __future__ import annotations

import sys
from pathlib import Path

from app.ocr.pipeline import process_pdf

BASE = Path(r"d:\HarshalProjects\Projects\01 - ROBO1040 - All Documents\01 - ROBO - Sample PDF Document - 10 Set")

CASES = [
    (
        "W-2",
        BASE / "01 - Form W-2 - Sample Document (10 Set)" / "01 - Document - Form W-2.pdf",
        {
            "Employee's first name and initial": "Thomas",
            "Last name": "Masi",
            "1 Wages, tips, other compensation": "2800.00",
            "2 Federal income tax withheld": "1365.22",
            "Employer identification number (EIN)": "57-1110444",
            "Employee's social security number": "XXX-XX-2930",
            "Year": "2024",
            "Control number": "20230218",
        },
    ),
    (
        "1099-INT-01",
        BASE / "03 - Form 1099-INT - Sample Document (10 Set)" / "01 - Document - Form 1099-INT.pdf",
        {
            "Recipient's Name": "TIMMERMAN",
            "Recipient's Street Address (including apt. no.)": "GATE POST",
            "1 Interest Income": "8986.68",
            "Payer's TIN": "11-2869526",
            "Recipient's TIN": "XXX-XX-4860",
            "Account Number": "XXXXXX6333",
            "PAYER'S name, address, and telephone": "BANK",
            "Year": "2024",
        },
    ),
    (
        "1099-INT-02",
        BASE / "03 - Form 1099-INT - Sample Document (10 Set)" / "02 - Document - Form 1099-INT.pdf",
        {
            "Recipient's Name": "MICHELLE",
            "Recipient's Street Address (including apt. no.)": "ROYAL COLONY",
            "1 Interest Income": "3909.17",
            "Payer's TIN": "20-1001796",
            "Recipient's TIN": "XXX-XX-4300",
            "PAYER'S name, address, and telephone": "BANK",
            "Account Number": "2211545799",
            "Year": "2024",
        },
    ),
    (
        "1099-DIV",
        BASE / "02 - Form 1099-DIV - Sample Document (10 Set)" / "01 - Document - Form 1099-DIV.pdf",
        {
            "Year": "2024",
            "1a Total ordinary dividends": "342.66",
            "1b Qualified dividends": "342.66",
            "Recipient's Name": "PERROTT",
            "Account Number": "C0042388017",
            "Payer's TIN": "51-6516897",
            "PAYER'S name, address, and telephone": "CUSTODIAN",
            "Recipient's Street Address (including apt. no.)": "PRESIDENTIAL",
        },
    ),
    (
        "5498-SA",
        BASE / "05 - Form 5498-SA - Sample Document (10 Set)" / "01 - Document - Form 5498-SA.pdf",
        {
            "Year": "2024",
            "PARTICIPANT'S name": "Daniel",
            "Street address (including apt. no.)": "CORN PLANTERS",
            "City, state, and ZIP": "DANIEL ISLAND",
            "Account number": "411464244",
            "5 FMV of HSA, Archer MSA, or MA MSA": "888.68",
            "6 HSA": "Yes",
            "TRUSTEE'S or ISSUER'S name, street address, city, state, ZIP": "Bank",
        },
    ),
    (
        "Brokerage",
        BASE / "04 - Consolidated Brokerage Statement - Sample Document (10 Set)" / "08 - Document - Consolidated Brokerage Statement.pdf",
        {
            "Year": "2024",
            "Account Number": "6852-5051",
            "Recipient's Name": "CLIFTON",
            "Recipient's Street Address (including apt. no.)": "SOUTHWOLD",
            "Recipient City": "GOOSE CREEK",
            "1a Total ordinary dividends": "598.71",
            "1b Qualified dividends": "598.71",
            "Payer Name": "CO",
        },
    ),
]


def score(fields: dict, expected: dict[str, str]) -> tuple[float, list[str], list[str]]:
    hits, misses = [], []
    for k, needle in expected.items():
        val = str(fields.get(k) or "")
        if needle.lower() in val.lower():
            hits.append(k)
        else:
            misses.append(f"{k}: got={val!r}")
    return len(hits) / len(expected), hits, misses


def main() -> int:
    all_ok = True
    for name, path, expected in CASES:
        print(f"\n=== {name} ===")
        if not path.exists():
            print("MISSING", path)
            all_ok = False
            continue
        cls, doc, fields, _conf = process_pdf(path.read_bytes())
        pct, _, misses = score(fields, expected)
        status = "PASS>=90%" if pct >= 0.90 else "BELOW 90%"
        print(f"form={cls.form_type} score={pct*100:.1f}% ({int(pct*len(expected))}/{len(expected)}) {status}")
        for m in misses:
            print("  MISS", m)
            all_ok = False
        if pct < 0.90:
            all_ok = False
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
