"""Render and dump text for remaining 5498-SA review PDFs."""

from __future__ import annotations

from pathlib import Path

import fitz

BASE = Path(
    r"D:\HarshalProjects\Projects\01 - ROBO1040 - All Documents"
    r"\01 - ROBO - Sample PDF Document - 10 Set"
    r"\05 - 5498 SA - Sample Document (10 Set)"
)
OUT = Path("training/review_dumps/sa_pages")
FILES = [
    "02 - Document - Form 5498 - SA.pdf",
    "07 - Document - Form 5498 - SA.pdf",
    "09 - Document - Form 5498 - SA.pdf",
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        pdf = BASE / name
        doc = fitz.open(pdf)
        print(f"=== {name}: pages={doc.page_count} size={pdf.stat().st_size}")
        dump_lines = [f"=== {name}: pages={doc.page_count} ==="]
        for i, page in enumerate(doc):
            text = page.get_text("text")
            print(f"--- page {i+1} text_len={len(text.strip())} ---")
            print(text[:2000] if text.strip() else "(no text)")
            dump_lines.append(f"\n--- page {i+1} ---\n")
            dump_lines.append(text if text.strip() else "(no text)")
            pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
            stem = name.replace(" ", "_").replace(".pdf", "")
            img_path = OUT / f"{stem}_p{i+1}.png"
            pix.save(str(img_path))
            print(f"saved {img_path} ({pix.width}x{pix.height})")
        dump_path = OUT / f"{name.replace(' ', '_').replace('.pdf','')}.txt"
        dump_path.write_text("\n".join(dump_lines), encoding="utf-8")
        doc.close()


if __name__ == "__main__":
    main()
