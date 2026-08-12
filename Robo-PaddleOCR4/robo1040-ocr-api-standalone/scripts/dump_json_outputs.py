"""CLI Utility: Process any tax form PDF and export OCR JSON + Final JSON into output_json/ directory."""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from app.ocr.json_exporter import save_output_jsons
from app.ocr.pipeline import process_pdf


def dump_pdf_json(pdf_path: str | Path) -> None:
    path = Path(pdf_path)
    if not path.is_file():
        print(f"Error: File not found -> {path}")
        sys.exit(1)

    print(f"Processing PDF: {path.name}...")
    pdf_bytes = path.read_bytes()

    start = time.perf_counter()
    classification, doc, fields, field_confidence = process_pdf(pdf_bytes)
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    preview = doc.ocr.full_text.strip().replace("\n", " ")
    if len(preview) > 500:
        preview = preview[:500] + "..."

    final_payload = {
        "form_type": classification.form_type,
        "confidence": classification.confidence,
        "processing_ms": elapsed_ms,
        "page_count": doc.ocr.page_count,
        "extraction_source": doc.source,
        "fields": fields,
        "field_confidence": field_confidence,
        "raw_text_preview": preview or None,
    }

    ocr_file, final_file = save_output_jsons(
        doc=doc,
        extract_response_dict=final_payload,
        output_dir="output_json",
        base_name=path.stem,
    )

    print("\nExtraction Complete!")
    print(f"  - Classified Form: {classification.form_type} (Confidence: {classification.confidence})")
    print(f"  - Processing Time: {elapsed_ms} ms")
    print(f"  - Extraction Source: {doc.source}")
    print(f"  - Total Fields Extracted: {len(fields)}")
    print("\nSaved Output Files:")
    print(f"  1. Raw OCR JSON  -> {ocr_file.resolve()}")
    print(f"  2. Final JSON    -> {final_file.resolve()}")
    print(f"  3. Generic View  -> {ocr_file.parent / 'ocr_result.json'}")
    print(f"  4. Generic View  -> {final_file.parent / 'final_extract.json'}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_pdf = sys.argv[1]
    else:
        # Default sample fixture
        fixture_path = root / "tests" / "fixtures" / "w2.txt"
        print("Usage: python scripts/dump_json_outputs.py path/to/tax_form.pdf")
        sys.exit(0)

    dump_pdf_json(target_pdf)
