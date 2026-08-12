"""Retest previously failing sample PDFs against live API."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1].parent / "01 - ROBO - Sample PDF Document - 10 Set"

FAILS = [
    ("W-2", "01 - W2 Form - Sample Document (10 Set)", "09 - Document - Form W-2.pdf", "W-2"),
    ("W-2", "01 - W2 Form - Sample Document (10 Set)", "10 - Document - Form W-2.pdf", "W-2"),
    ("1099-INT", "02 - 1099 INT - Sample Document (10 Set)", "07 - Document - 1099 - INT.pdf", "1099-INT"),
    ("1099-INT", "02 - 1099 INT - Sample Document (10 Set)", "09 - Document - 1099 - INT.pdf", "1099-INT"),
    ("1099-DIV", "03 - 1099 DIV - Sample Document (10 Set)", "05 - Document - 1099 - DIV.pdf", "1099-DIV"),
    (
        "Brokerage",
        "04 - Consolidated Brokerage Statement - Sample Document (10 Set)",
        "01 - Document - Consolidated Brokerage Statement.pdf",
        "Consolidated Brokerage Statement",
    ),
    (
        "Brokerage",
        "04 - Consolidated Brokerage Statement - Sample Document (10 Set)",
        "10 - Document - Consolidated Brokerage Statement.pdf",
        "Consolidated Brokerage Statement",
    ),
    ("5498-SA", "05 - 5498 SA - Sample Document (10 Set)", "02 - Document - Form 5498 - SA.pdf", "5498-SA"),
    ("5498-SA", "05 - 5498 SA - Sample Document (10 Set)", "03 - Document - Form 5498 - SA.pdf", "5498-SA"),
    ("5498-SA", "05 - 5498 SA - Sample Document (10 Set)", "05 - Document - Form 5498 - SA.pdf", "5498-SA"),
    ("5498-SA", "05 - 5498 SA - Sample Document (10 Set)", "07 - Document - Form 5498 - SA.pdf", "5498-SA"),
    ("5498-SA", "05 - 5498 SA - Sample Document (10 Set)", "09 - Document - Form 5498 - SA.pdf", "5498-SA"),
]

KEY_FIELDS = {
    "W-2": [
        "Year",
        "Employee's first name and initial",
        "Last name",
        "Employer identification number (EIN)",
        "1 Wages, tips, other compensation",
    ],
    "1099-INT": [
        "Year",
        "Payer's TIN",
        "Recipient's TIN",
        "Recipient's Name",
        "Recipient's Street Address (including apt. no.)",
        "Account Number",
        "1 Interest Income",
    ],
    "1099-DIV": [
        "Year",
        "Payer's TIN",
        "Recipient's Name",
        "Account Number",
        "1a Total ordinary dividends",
    ],
    "5498-SA": [
        "Year",
        "PARTICIPANT'S name",
        "Street address (including apt. no.)",
        "Account number",
        "5 FMV of HSA, Archer MSA, or MA MSA",
    ],
    "Brokerage": [
        "Year",
        "Account Number",
        "Recipient's Name",
        "Recipient's Street Address (including apt. no.)",
        "Recipient City",
        "1a Total ordinary dividends",
    ],
}


def extract(pdf: Path) -> dict:
    cmd = [
        "curl.exe",
        "-s",
        "-H",
        "X-API-Key: robo1040",
        "-F",
        f"file=@{pdf};type=application/pdf",
        "http://127.0.0.1:8010/api/v1/extract",
    ]
    raw = subprocess.check_output(cmd, timeout=120)
    return json.loads(raw.decode("utf-8", errors="replace"))


def field_fill_rate(fields: dict, keys: list[str]) -> float:
    if not keys:
        return 0.0
    hit = sum(1 for k in keys if fields.get(k) not in (None, ""))
    return hit / len(keys)


def is_unfilled_template(fields: dict, keys: list[str]) -> bool:
    identity = [
        k
        for k in keys
        if any(
            x in k.lower()
            for x in (
                "name",
                "street",
                "city",
                "account",
                "wage",
                "dividend",
                "interest",
                "fmv",
                "ein",
            )
        )
    ]
    if not identity:
        return False
    return sum(1 for k in identity if fields.get(k) not in (None, "")) == 0


def main() -> int:
    passed = 0
    for label, folder, fname, expected in FAILS:
        pdf = BASE / folder / fname
        data = extract(pdf)
        fields = data.get("fields") or {}
        keys = KEY_FIELDS[label]
        fill = field_fill_rate(fields, keys)
        cls_ok = data.get("form_type") == expected
        blank = is_unfilled_template(fields, keys)
        ok = cls_ok and (fill >= 0.70 or blank)
        passed += int(ok)
        name = (
            fields.get("Recipient's Name")
            or fields.get("Employee's first name and initial")
            or fields.get("PARTICIPANT'S name")
        )
        print(
            f"{'PASS' if ok else 'FAIL'} {label:10} {fname[:36]:36} "
            f"type={data.get('form_type')} cls={cls_ok} fill={fill*100:.0f}% "
            f"{'BLANK ' if blank else ''}"
            f"name={str(name)[:40]!r} ms={data.get('processing_ms')}"
        )
        if not ok:
            missing = [k for k in keys if fields.get(k) in (None, "")]
            print(f"       missing={missing}")
    print(f"\nFixed sample pass={passed}/{len(FAILS)}")
    return 0 if passed == len(FAILS) else 1


if __name__ == "__main__":
    sys.exit(main())
