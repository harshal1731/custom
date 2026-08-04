"""Export empty ground-truth label template from ROBO FieldSpecs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ocr.form_specs import get_field_specs


FORM_TYPES = [
    "W-2",
    "1099-INT",
    "1099-DIV",
    "5498-SA",
    "Consolidated Brokerage Statement",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="Output JSON path")
    args = parser.parse_args()

    template: dict = {"_readme": "Fill fields per PDF filename. Null = unknown/missing."}
    for form_type in FORM_TYPES:
        fields = {spec.key: None for spec in get_field_specs(form_type)}
        template[f"_example_{form_type}"] = {"form_type": form_type, "fields": fields}

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(template, indent=2), encoding="utf-8")
    print(f"Wrote template -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
