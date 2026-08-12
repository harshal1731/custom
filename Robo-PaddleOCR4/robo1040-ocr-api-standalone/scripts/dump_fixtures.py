"""Dump OCR text fixtures from sample PDFs (run inside container or local venv)."""
from __future__ import annotations

from pathlib import Path

from app.ocr.engine import run_ocr

OUT = Path("/tmp/ocr_fixtures")
SAMPLES = {
    "w2": "/tmp/w2.pdf",
    "1099_int": "/tmp/int.pdf",
    "1099_div": "/tmp/div.pdf",
    "5498_sa": "/tmp/sa.pdf",
    "brokerage": "/tmp/broker.pdf",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, pdf in SAMPLES.items():
        p = Path(pdf)
        if not p.exists():
            print("missing", pdf)
            continue
        text = run_ocr(p.read_bytes()).full_text
        out = OUT / f"{name}.txt"
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out} chars={len(text)}")


if __name__ == "__main__":
    main()
