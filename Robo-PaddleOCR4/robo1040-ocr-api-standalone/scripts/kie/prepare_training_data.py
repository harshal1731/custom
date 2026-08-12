"""Prepare KIE training data from labeled PDF ground truth (IRS labels only)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare VI-LayoutXLM KIE training data")
    parser.add_argument("--pdf-dir", required=True, help="Directory of sample PDFs")
    parser.add_argument("--labels", required=True, help="Ground truth JSON (filename -> fields)")
    parser.add_argument("--out-dir", required=True, help="Output directory for KIE training set")
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    labels = json.loads(Path(args.labels).read_text(encoding="utf-8"))
    entries: list[dict] = []

    for filename, fields in labels.items():
        pdf_path = pdf_dir / filename
        if not pdf_path.exists():
            print(f"SKIP missing: {filename}")
            continue
        pairs = [{"field_key": k, "label": k, "value": v} for k, v in fields.items() if v]
        entries.append({"file": filename, "pairs": pairs})

    manifest = {"samples": entries, "entity_classes": ["QUESTION", "ANSWER"]}
    out_path = out_dir / "kie_manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    class_list = out_dir / "class_list.txt"
    class_list.write_text("QUESTION\nANSWER\n", encoding="utf-8")

    print(f"Wrote {len(entries)} samples -> {out_path}")
    print(f"Class list -> {class_list}")
    print("Next: convert to XFUND format and run PaddleOCR ppstructure/kie training.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
