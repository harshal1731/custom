"""Dump local pipeline text for failing samples."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ocr.document_loader import load_document
from app.ocr.classifier import classify_form
from app.ocr.pipeline import process_pdf

BASE = Path(__file__).resolve().parents[1].parent / "01 - ROBO - Sample PDF Document - 10 Set"
OUT = Path("training/review_dumps/fail_ocr")
SAMPLES = [
    ("01 - W2 Form - Sample Document (10 Set)", "09 - Document - Form W-2.pdf"),
    ("01 - W2 Form - Sample Document (10 Set)", "10 - Document - Form W-2.pdf"),
    ("02 - 1099 INT - Sample Document (10 Set)", "07 - Document - 1099 - INT.pdf"),
    ("02 - 1099 INT - Sample Document (10 Set)", "09 - Document - 1099 - INT.pdf"),
    ("03 - 1099 DIV - Sample Document (10 Set)", "05 - Document - 1099 - DIV.pdf"),
    ("04 - Consolidated Brokerage Statement - Sample Document (10 Set)", "01 - Document - Consolidated Brokerage Statement.pdf"),
    ("04 - Consolidated Brokerage Statement - Sample Document (10 Set)", "10 - Document - Consolidated Brokerage Statement.pdf"),
    ("05 - 5498 SA - Sample Document (10 Set)", "02 - Document - Form 5498 - SA.pdf"),
    ("05 - 5498 SA - Sample Document (10 Set)", "03 - Document - Form 5498 - SA.pdf"),
    ("05 - 5498 SA - Sample Document (10 Set)", "05 - Document - Form 5498 - SA.pdf"),
    ("05 - 5498 SA - Sample Document (10 Set)", "07 - Document - Form 5498 - SA.pdf"),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for folder, fname in SAMPLES:
        pdf = BASE / folder / fname
        data = pdf.read_bytes()
        loaded = load_document(data, max_pages=2)
        text = loaded.ocr.full_text if hasattr(loaded.ocr, "full_text") else "\n".join(
            p.text for p in loaded.ocr.pages
        )
        cls = classify_form(text)
        stem = fname.replace(" ", "_").replace(".pdf", "")
        out = OUT / f"{stem}.txt"
        out.write_text(
            f"source={loaded.source} form={cls.form_type} chars={len(text)}\n\n{text[:8000]}",
            encoding="utf-8",
        )
        print(f"{fname}: source={loaded.source} cls={cls.form_type} chars={len(text)} -> {out}")


if __name__ == "__main__":
    main()
