from app.config import get_settings
import httpx
import json

key = get_settings().api_key
r = httpx.post(
    "http://127.0.0.1:8000/api/v1/extract",
    headers={"X-API-Key": key},
    files={"file": ("w2.pdf", open("/tmp/w2.pdf", "rb"), "application/pdf")},
    timeout=180.0,
)
print("status", r.status_code)
d = r.json()
print("ms", d.get("processing_ms"), "form", d.get("form_type"))
f = d.get("fields", {})
keys = [
    "Year",
    "Employee's social security number",
    "Employer identification number (EIN)",
    "Employer's name, address, and ZIP code",
    "Control number",
    "Employee's first name and initial",
    "Last name",
    "Employee's address and ZIP code",
    "1 Wages, tips, other compensation",
    "2 Federal income tax withheld",
    "3 Social security wages",
    "4 Social security tax withheld",
    "5 Medicare wages and tips",
    "6 Medicare tax withheld",
    "15 State / Employer's state ID number",
    "16 State wages, tips, etc.",
    "17 State income tax",
]
for k in keys:
    print(f"{k}: {f.get(k)}")
