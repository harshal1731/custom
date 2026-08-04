"""Quick accuracy smoke for all sample form types."""
from __future__ import annotations

from pathlib import Path

from app.ocr.pipeline import process_pdf

SAMPLES = {
    "W-2": "/tmp/w2.pdf",
    "1099-INT": "/tmp/int.pdf",
    "1099-DIV": "/tmp/div.pdf",
    "5498-SA": "/tmp/sa.pdf",
    "Brokerage": "/tmp/broker.pdf",
}

IDENTITY_KEYS = [
    "PAYER'S name, address, and telephone",
    "Payer Name",
    "Recipient's Name",
    "PARTICIPANT'S name",
    "Employee's first name and initial",
    "Employer's name, address, and ZIP code",
    "Recipient's Street Address (including apt. no.)",
    "Street address (including apt. no.)",
    "Account Number",
    "Account number",
]


def main() -> None:
    for label, path in SAMPLES.items():
        p = Path(path)
        if not p.exists():
            print(f"{label}: SKIP (missing {path})")
            continue
        cls, doc, fields, _conf = process_pdf(p.read_bytes())
        filled = sum(1 for v in fields.values() if v not in (None, "", []))
        total = len(fields)
        identity = {k: fields.get(k) for k in IDENTITY_KEYS if k in fields}
        print(f"\n=== {label} -> {cls.form_type} ({cls.confidence}) filled={filled}/{total} ===")
        for k, v in identity.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
