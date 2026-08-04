"""Dump PaddleOCR text for W-2 sample to tune extractors."""
from app.ocr.pipeline import process_pdf

pdf = open("/tmp/w2.pdf", "rb").read()
cls, doc, fields, _conf = process_pdf(pdf)
ocr = doc.ocr
print("FORM", cls.form_type, cls.confidence)
print("==== FULL TEXT ====")
print(ocr.full_text)
print("==== FIELDS ====")
for k, v in fields.items():
    print(f"{k}: {v}")
