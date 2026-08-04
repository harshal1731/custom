import fitz
from pathlib import Path

BASE = Path("d:/HarshalProjects/Projects/01 - ROBO1040 - All Documents/01 - ROBO - Sample PDF Document - 10 Set")
FILES = [
    BASE / "01 - W2 Form - Sample Document (10 Set)/03 - Document - Form W-2.pdf",
    BASE / "01 - W2 Form - Sample Document (10 Set)/09 - Document - Form W-2.pdf",
    BASE / "01 - W2 Form - Sample Document (10 Set)/10 - Document - Form W-2.pdf",
    BASE / "04 - Consolidated Brokerage Statement - Sample Document (10 Set)/08 - Document - Consolidated Brokerage Statement.pdf",
    BASE / "04 - Consolidated Brokerage Statement - Sample Document (10 Set)/09 - Document - Consolidated Brokerage Statement.pdf",
    BASE / "04 - Consolidated Brokerage Statement - Sample Document (10 Set)/01 - Document - Consolidated Brokerage Statement.pdf",
    BASE / "05 - 5498 SA - Sample Document (10 Set)/03 - Document - Form 5498 - SA.pdf",
    BASE / "05 - 5498 SA - Sample Document (10 Set)/06 - Document - Form 5498 - SA.pdf",
    BASE / "02 - 1099 INT - Sample Document (10 Set)/07 - Document - 1099 - INT.pdf",
]

for pdf in FILES:
    print(f"\n{'='*80}\n=== {pdf.name} ===\n{'='*80}")
    if not pdf.exists():
        print("FILE NOT FOUND")
        continue
    try:
        doc = fitz.open(pdf)
        text = ""
        for page in doc:
            text += page.get_text("text") + "\n"
        print(text[:2000]) # First 2000 chars should be plenty for headers
    except Exception as e:
        print(e)
