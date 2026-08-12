"""Smoke-test live API against one PDF per form type."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import urllib.request

BASE = Path(__file__).resolve().parents[1].parent / "01 - ROBO - Sample PDF Document - 10 Set"
SAMPLES = [
    ("W-2", BASE / "01 - W2 Form - Sample Document (10 Set)" / "01 - Document - Form W-2.pdf"),
    ("1099-INT", BASE / "02 - 1099 INT - Sample Document (10 Set)" / "01 - Document - 1099 - INT.pdf"),
    ("1099-DIV", BASE / "03 - 1099 DIV - Sample Document (10 Set)" / "01 - Document - 1099 - DIV.pdf"),
    ("5498-SA", BASE / "05 - 5498 SA - Sample Document (10 Set)" / "01 - Document - Form 5498 - SA.pdf"),
    (
        "Brokerage",
        BASE
        / "04 - Consolidated Brokerage Statement - Sample Document (10 Set)"
        / "01 - Document - Consolidated Brokerage Statement.pdf",
    ),
]

SHOW = [
    "Year",
    "Employee's first name and initial",
    "Last name",
    "Employer's name, address, and ZIP code",
    "Employee's address and ZIP code",
    "1 Wages, tips, other compensation",
    "PAYER'S name, address, and telephone",
    "Recipient's Name",
    "Recipient's Street Address (including apt. no.)",
    "Account Number",
    "Account number",
    "1 Interest Income",
    "1a Total ordinary dividends",
    "PARTICIPANT'S name",
    "Street address (including apt. no.)",
    "5 FMV of HSA, Archer MSA, or MA MSA",
    "Payer Name",
    "Recipient City",
    "Recipient State",
]


def api_key() -> str:
    try:
        out = subprocess.check_output(
            ["docker", "exec", "robo1040-ocr-api", "printenv", "API_KEY"],
            text=True,
        ).strip()
        if out:
            return out
    except Exception:
        pass
    return os.environ.get("API_KEY", "robo1040")


def extract(pdf: Path, key: str) -> dict:
    # Use curl for multipart reliability on Windows
    cmd = [
        "curl.exe",
        "-s",
        "-H",
        f"X-API-Key: {key}",
        "-F",
        f"file=@{pdf};type=application/pdf",
        "http://127.0.0.1:8010/api/v1/extract",
    ]
    raw = subprocess.check_output(cmd)
    return json.loads(raw.decode("utf-8", errors="replace"))


def main() -> int:
    key = api_key()
    ok = True
    for label, path in SAMPLES:
        print(f"\n=== {label} ===")
        if not path.exists():
            print("MISSING", path)
            ok = False
            continue
        data = extract(path, key)
        print(
            "form_type:",
            data.get("form_type"),
            "conf:",
            data.get("confidence"),
            "ms:",
            data.get("processing_ms"),
        )
        fields = data.get("fields") or {}
        for k in SHOW:
            if fields.get(k) is not None:
                print(f"  {k}: {fields[k]}")
        if data.get("form_type") in (None, "Unknown"):
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
