import subprocess
import json
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
    print(f"--- {pdf.name} ---")
    if not pdf.exists():
        print("FILE NOT FOUND")
        continue
    cmd = [
        "curl.exe",
        "-s",
        "-H", "X-API-Key: robo1040",
        "-F", f"file=@{pdf};type=application/pdf",
        "http://127.0.0.1:8010/api/v1/extract",
    ]
    raw = subprocess.check_output(cmd)
    data = json.loads(raw.decode("utf-8", errors="replace"))
    
    preview = data.get("raw_text_preview", "") or ""
    print(f"Preview: {preview[:150]}...")
    
    fields = data.get("fields", {})
    missing = [k for k, v in fields.items() if not v]
    filled = {k: v for k, v in fields.items() if v}
    print(f"Filled: {json.dumps(filled, indent=2)}")
    print(f"Missing: {missing}")
    print()
