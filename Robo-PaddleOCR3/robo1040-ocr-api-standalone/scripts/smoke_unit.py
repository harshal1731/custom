from app.ocr.classifier import classify_form
from app.ocr.extractors.w2 import extract_w2

r = classify_form(
    "Form W-2 Wage and Tax Statement Social security wages Employer identification number"
)
print("classify", r)

f = extract_w2(
    "Form W-2 2023 SSN 123-45-6789 EIN 12-3456789 "
    "Wages, tips, other compensation $50,000.00"
)
print(
    "ssn",
    f["Employee's social security number"],
    "ein",
    f["Employer identification number (EIN)"],
    "year",
    f["Year"],
    "wages",
    f["1 Wages, tips, other compensation"],
)
print("OK")
