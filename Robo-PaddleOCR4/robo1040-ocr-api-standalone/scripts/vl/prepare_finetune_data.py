"""Build fine-tune package from labeled tax PDFs (IRS fields only)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ocr.schema_extract import schema_for_form


def _find_pdf(pdf_dir: Path, filename: str) -> Path | None:
    direct = pdf_dir / filename
    if direct.exists():
        return direct
    matches = list(pdf_dir.rglob(filename))
    return matches[0] if matches else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare VL/schema fine-tune data")
    parser.add_argument("--pdf-dir", required=True)
    parser.add_argument("--labels", required=True, help="ground_truth.json")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    out_dir = Path(args.out_dir)
    schemas_dir = out_dir / "schemas"
    prompts_dir = out_dir / "prompts"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    labels = json.loads(Path(args.labels).read_text(encoding="utf-8"))
    samples: list[dict] = []
    jsonl_lines: list[str] = []

    for filename, payload in labels.items():
        if filename.startswith("_"):
            continue
        if not isinstance(payload, dict):
            continue

        if "fields" in payload:
            form_type = str(payload.get("form_type") or "Unknown")
            fields = payload.get("fields") or {}
        else:
            form_type = str(payload.get("form_type") or "Unknown")
            fields = {k: v for k, v in payload.items() if k != "form_type"}

        if not isinstance(fields, dict):
            continue

        pdf_path = _find_pdf(pdf_dir, filename)
        if pdf_path is None:
            print(f"SKIP missing PDF: {filename}")
            continue

        samples.append(
            {
                "file": filename,
                "path": str(pdf_path),
                "form_type": form_type,
                "fields": fields,
            }
        )

        keys = list(fields.keys())
        user = (
            "Extract US tax form fields as JSON only.\n"
            f"form_type: {form_type}\n"
            f"fields: {json.dumps(keys)}\n"
            f"document_file: {filename}\n"
        )
        assistant = json.dumps(fields, ensure_ascii=False)
        jsonl_lines.append(
            json.dumps(
                {
                    "messages": [
                        {"role": "system", "content": "You extract tax form fields as JSON only."},
                        {"role": "user", "content": user},
                        {"role": "assistant", "content": assistant},
                    ]
                },
                ensure_ascii=False,
            )
        )

    # Write per-form schemas
    form_types = sorted({s["form_type"] for s in samples if s["form_type"] != "Unknown"})
    for ft in form_types:
        schema = schema_for_form(ft)
        (schemas_dir / f"{ft.replace(' ', '_')}.json").write_text(
            json.dumps(schema, indent=2), encoding="utf-8"
        )

    manifest = {
        "samples": samples,
        "count": len(samples),
        "form_types": form_types,
        "entity_classes": ["QUESTION", "ANSWER"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "class_list.txt").write_text("QUESTION\nANSWER\n", encoding="utf-8")
    (prompts_dir / "schema_sft.jsonl").write_text("\n".join(jsonl_lines) + ("\n" if jsonl_lines else ""), encoding="utf-8")

    print(f"Samples: {len(samples)}")
    print(f"Manifest -> {out_dir / 'manifest.json'}")
    print(f"Schemas  -> {schemas_dir}")
    print(f"SFT JSONL -> {prompts_dir / 'schema_sft.jsonl'}")
    print("Next: fine-tune VL / local LLM / LayoutXLM — see scripts/vl/README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
