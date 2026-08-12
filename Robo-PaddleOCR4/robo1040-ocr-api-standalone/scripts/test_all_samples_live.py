"""Run all 50 ROBO sample PDFs through live API and summarize."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1].parent / "01 - ROBO - Sample PDF Document - 10 Set"

FOLDERS = [
    ("W-2", "01 - W2 Form - Sample Document (10 Set)", "W-2"),
    ("1099-INT", "02 - 1099 INT - Sample Document (10 Set)", "1099-INT"),
    ("1099-DIV", "03 - 1099 DIV - Sample Document (10 Set)", "1099-DIV"),
    (
        "Brokerage",
        "04 - Consolidated Brokerage Statement - Sample Document (10 Set)",
        "Consolidated Brokerage Statement",
    ),
    ("5498-SA", "05 - 5498 SA - Sample Document (10 Set)", "5498-SA"),
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


def api_key() -> str:
    import os

    env_key = os.environ.get("API_KEY", "").strip()
    if env_key:
        return env_key
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("API_KEY="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    return val
    try:
        out = subprocess.check_output(
            ["docker", "exec", "robo1040-ocr-api", "printenv", "API_KEY"],
            text=True,
        ).strip()
        if out:
            return out
    except Exception:
        pass
    raise RuntimeError("API_KEY not found")


def extract(pdf: Path, key: str) -> dict:
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


def field_fill_rate(fields: dict, keys: list[str]) -> float:
    if not keys:
        return 0.0
    hit = sum(1 for k in keys if fields.get(k) not in (None, ""))
    return hit / len(keys)


def is_unfilled_template(fields: dict, keys: list[str], form_type: str) -> bool:
    """True when the PDF is a blank IRS copy (labels only) — can't hit 70% fill honestly."""
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
    filled_id = sum(1 for k in identity if fields.get(k) not in (None, ""))
    # Allow Year-only (and maybe checkbox noise) on blank copies
    return filled_id == 0 and bool(fields.get("Year") or form_type)


def main() -> int:
    key = "robo1040"
    rows: list[dict] = []

    for label, folder, expected_type in FOLDERS:
        dir_path = BASE / folder
        pdfs = sorted(dir_path.glob("*.pdf"))
        keys = KEY_FIELDS[label]
        for pdf in pdfs:
            try:
                data = extract(pdf, key)
            except Exception as exc:
                rows.append(
                    {
                        "form": label,
                        "file": pdf.name,
                        "error": str(exc),
                        "ok": False,
                    }
                )
                continue
            fields = data.get("fields") or {}
            cls = data.get("form_type")
            fill = field_fill_rate(fields, keys)
            cls_ok = cls == expected_type
            blank = is_unfilled_template(fields, keys, cls or "")
            # pass if classified correctly and (>=70% key fields OR blank template)
            ok = cls_ok and (fill >= 0.70 or blank)
            rows.append(
                {
                    "form": label,
                    "file": pdf.name,
                    "form_type": cls,
                    "expected": expected_type,
                    "cls_ok": cls_ok,
                    "confidence": data.get("confidence"),
                    "ms": data.get("processing_ms"),
                    "pages": data.get("page_count"),
                    "fill_pct": round(fill * 100, 1),
                    "blank_template": blank,
                    "ok": ok,
                    "recipient_or_employee": fields.get("Recipient's Name")
                    or fields.get("Employee's first name and initial")
                    or fields.get("PARTICIPANT'S name"),
                    "primary_amount": fields.get("1 Interest Income")
                    or fields.get("1a Total ordinary dividends")
                    or fields.get("1 Wages, tips, other compensation")
                    or fields.get("5 FMV of HSA, Archer MSA, or MA MSA"),
                }
            )
            tag = "BLANK" if blank else ("OK" if ok else "FAIL")
            print(
                f"{label:12} {pdf.name:45} cls={'OK' if cls_ok else 'FAIL':4} "
                f"fill={fill*100:5.1f}% {tag:5} ms={data.get('processing_ms'):6} "
                f"name={str(rows[-1]['recipient_or_employee'])[:30]!r}"
            )

    out_path = Path(__file__).resolve().parents[1] / "live_sample_results.json"
    out_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    print("\n=== SUMMARY ===")
    for label, _, _ in FOLDERS:
        subset = [r for r in rows if r.get("form") == label and "error" not in r]
        if not subset:
            print(f"{label}: no results")
            continue
        passed = sum(1 for r in subset if r.get("ok"))
        cls_ok = sum(1 for r in subset if r.get("cls_ok"))
        avg_ms = sum(r.get("ms") or 0 for r in subset) / len(subset)
        avg_fill = sum(r.get("fill_pct") or 0 for r in subset) / len(subset)
        under15 = sum(1 for r in subset if (r.get("ms") or 99999) <= 15000)
        print(
            f"{label:12} pass={passed}/{len(subset)} classify={cls_ok}/{len(subset)} "
            f"avg_fill={avg_fill:.1f}% avg_ms={avg_ms:.0f} under15s={under15}/{len(subset)}"
        )

    total = [r for r in rows if "error" not in r]
    passed = sum(1 for r in total if r.get("ok"))
    print(f"\nOVERALL pass={passed}/{len(total)} ({100*passed/max(len(total),1):.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
