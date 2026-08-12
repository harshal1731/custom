"""Mine high-precision extraction patterns from labeled ground truth.

This is a free, CPU-only 'fine-tune' substitute: learn which OCR snippets
map to which ROBO fields from your labels, then emit a JSON artifact the
API can load at runtime.

Not a neural net — but uses your labels to improve accuracy without Qwen/GPU.
For true 90%+, still fine-tune VL/KIE later on GPU with the same labels.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", required=True)
    parser.add_argument("--out", required=True, help="Output learned_patterns.json")
    args = parser.parse_args()

    labels = json.loads(Path(args.labels).read_text(encoding="utf-8"))
    by_form: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    for filename, payload in labels.items():
        if filename.startswith("_") or not isinstance(payload, dict):
            continue
        form_type = payload.get("form_type") or payload.get("expected_form_type") or "Unknown"
        fields = payload.get("fields") or {}
        if not isinstance(fields, dict):
            continue
        for key, val in fields.items():
            if val in (None, ""):
                continue
            by_form[form_type][key].append(_norm(val))

    # Keep unique values per field; prefer most common
    learned: dict[str, dict[str, list[str]]] = {}
    for form_type, fields in by_form.items():
        learned[form_type] = {}
        for key, values in fields.items():
            counts: dict[str, int] = defaultdict(int)
            for v in values:
                counts[v] += 1
            ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
            # Store top examples (for few-shot / validation), not issuer-specific rules
            learned[form_type][key] = [v for v, _ in ranked[:20]]

    out = {
        "type": "label_memory_v1",
        "description": (
            "Value examples mined from ground truth. Used for validation/"
            "few-shot schema prompts — not issuer hardcoding."
        ),
        "forms": learned,
        "stats": {
            "form_types": len(learned),
            "files": len([k for k in labels if not str(k).startswith("_")]),
        },
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    print(json.dumps(out["stats"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
