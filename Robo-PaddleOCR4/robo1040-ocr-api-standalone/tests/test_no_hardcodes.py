"""Guard: production OCR code must not embed issuer/person sample literals."""

from __future__ import annotations

from pathlib import Path

FORBIDDEN = [
    "AMERICAN EXPRESS",
    "ALLY BANK",
    "WELLS FARGO",
    "COMPUTERSHARE",
    "CHARLES SCHWAB",
    "Optum Bank",
    "Optum Financial",
    "HEATH B TIMMERMAN",
    "MICHELLE L RODRIGUEZ",
    "THOMAS R PERROTT",
    "CLIFTON WENDELL POSTON",
    "Daniel Sommer",
    "Goldman Sachs",
]

APP_OCR = Path(__file__).resolve().parents[1] / "app" / "ocr"


def test_no_issuer_or_person_hardcodes_in_app_ocr():
    offenders: list[str] = []
    for path in APP_OCR.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in FORBIDDEN:
            if needle in text or needle.lower() in text.lower():
                # allow comments? No — production must stay clean
                offenders.append(f"{path.relative_to(APP_OCR.parent.parent)}: {needle}")
    assert not offenders, "Hardcoded issuer/person literals found:\n" + "\n".join(offenders)
