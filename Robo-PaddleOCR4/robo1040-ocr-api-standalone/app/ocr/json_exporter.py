"""JSON exporter utility to dump OCR JSON and Final JSON into output_json/ folder."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.ocr.types import DocumentLoadResult, OcrResult


def ocr_to_dict(ocr: OcrResult) -> dict[str, Any]:
    """Convert OcrResult dataclass to JSON-serializable dictionary with tokens & coords."""
    return {
        "source": ocr.source,
        "page_count": ocr.page_count,
        "markdown": ocr.markdown,
        "full_text": ocr.full_text,
        "pages": [
            {
                "page_number": p.page_number,
                "width": p.width,
                "height": p.height,
                "text": p.text,
                "lines": p.lines,
                "tokens": [
                    {
                        "text": t.text,
                        "confidence": round(t.confidence, 4),
                        "left": t.left,
                        "top": t.top,
                        "right": t.right,
                        "bottom": t.bottom,
                    }
                    for t in p.tokens
                ],
                "layout_regions": [
                    {
                        "label": r.label,
                        "left": r.left,
                        "top": r.top,
                        "right": r.right,
                        "bottom": r.bottom,
                        "score": round(r.score, 4),
                    }
                    for r in p.layout_regions
                ],
            }
            for p in ocr.pages
        ],
        "kie_pairs": [
            {
                "field_key": k.field_key,
                "label": k.label,
                "value": k.value,
                "confidence": round(k.confidence, 4),
                "method": k.method,
            }
            for k in ocr.kie_pairs
        ],
    }


def save_output_jsons(
    doc: DocumentLoadResult,
    extract_response_dict: dict[str, Any],
    output_dir: str | Path = "output_json",
    base_name: str | None = None,
) -> tuple[Path, Path]:
    """Save both OCR JSON and Final Extract JSON into the output_json/ folder."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    ocr_dict = ocr_to_dict(doc.ocr)

    prefix = f"{base_name}_" if base_name else ""
    ocr_file = out_path / f"{prefix}ocr_result.json"
    final_file = out_path / f"{prefix}final_extract.json"

    ocr_file.write_text(json.dumps(ocr_dict, indent=2, ensure_ascii=False), encoding="utf-8")
    final_file.write_text(json.dumps(extract_response_dict, indent=2, ensure_ascii=False), encoding="utf-8")

    # Also update generic files for easy viewing
    if base_name:
        (out_path / "ocr_result.json").write_text(json.dumps(ocr_dict, indent=2, ensure_ascii=False), encoding="utf-8")
        (out_path / "final_extract.json").write_text(json.dumps(extract_response_dict, indent=2, ensure_ascii=False), encoding="utf-8")

    return ocr_file, final_file
