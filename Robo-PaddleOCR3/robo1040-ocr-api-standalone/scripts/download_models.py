"""Download PaddleOCR mobile + PP-StructureV3 models (run once at image build / startup)."""

from __future__ import annotations

import sys
from pathlib import Path


def _model_ready(name: str) -> bool:
    root = Path.home() / ".paddlex" / "official_models"
    path = root / name
    return (path / "inference.yml").exists() or (path / "inference.json").exists()


def _ocr_models_ready() -> bool:
    return _model_ready("PP-OCRv5_mobile_det") and _model_ready("PP-OCRv5_mobile_rec")


def main() -> int:
    if _ocr_models_ready():
        print("PaddleOCR mobile models already cached — skipping OCR download.")
    else:
        from paddleocr import PaddleOCR
        import numpy as np

        print("Downloading PP-OCRv5 mobile models...")
        ocr = PaddleOCR(
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="PP-OCRv5_mobile_rec",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        blank = np.zeros((64, 64, 3), dtype=np.uint8)
        ocr.predict(blank)

    root = Path.home() / ".paddlex" / "official_models"
    for name in ("PP-OCRv5_mobile_det", "PP-OCRv5_mobile_rec"):
        path = root / name
        ok = (path / "inference.yml").exists() or (path / "inference.json").exists()
        print(f"{name}: {'OK' if ok else 'MISSING'} -> {path}")
        if not ok:
            raise RuntimeError(f"Model not cached: {path}")

    # PP-StructureV3 layout models are large and may fail offline during build.
    # Lazy-load at runtime; document_loader falls back to PaddleOCR if structure fails.
    print("PP-StructureV3 warmup deferred to runtime (lazy-load with OCR fallback).")

    print("All models ready.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"MODEL DOWNLOAD FAILED: {exc}", file=sys.stderr)
        raise
