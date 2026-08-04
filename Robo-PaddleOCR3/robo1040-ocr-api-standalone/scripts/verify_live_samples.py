"""Verify live container extraction on key PDFs (runs inside Docker)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.ocr.pipeline import process_pdf

SAMPLES = [
    ("W-2", Path("/tmp/samples/w2.pdf")),
    ("INT-01", Path("/tmp/samples/int01.pdf")),
    ("INT-02", Path("/tmp/samples/int02.pdf")),
]

SHOW = [
    "Year",
    "Employee's first name and initial",
    "Last name",
    "1 Wages, tips, other compensation",
    "PAYER'S name, address, and telephone",
    "Recipient's Name",
    "Recipient's Street Address (including apt. no.)",
    "Recipient's city, state, country and Zip code",
    "Account Number",
    "1 Interest Income",
    "Payer's TIN",
    "Recipient's TIN",
]


def main() -> int:
    ok = True
    for label, path in SAMPLES:
        print(f"\n=== {label} ===")
        if not path.exists():
            print("MISSING", path)
            ok = False
            continue
        cls, doc, fields, _conf = process_pdf(path.read_bytes())
        print("form_type:", cls.form_type, "conf:", cls.confidence)
        for k in SHOW:
            if fields.get(k) is not None:
                print(f"  {k}: {fields[k]}")
        if label == "INT-02":
            name = fields.get("Recipient's Name") or ""
            inc = fields.get("1 Interest Income")
            payer = fields.get("PAYER'S name, address, and telephone") or ""
            if "MICHELLE" not in name.upper() or inc != "3909.17" or "BANK" not in payer.upper():
                print("FAIL expectations for Ally combined statement")
                ok = False
        if label.startswith("INT") and cls.form_type != "1099-INT":
            ok = False
        if label == "W-2" and cls.form_type != "W-2":
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
