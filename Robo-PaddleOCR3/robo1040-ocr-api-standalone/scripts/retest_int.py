from app.config import get_settings
import httpx

key = get_settings().api_key
r = httpx.post(
    "http://127.0.0.1:8000/api/v1/extract",
    headers={"X-API-Key": key},
    files={"file": ("int.pdf", open("/tmp/int.pdf", "rb"), "application/pdf")},
    timeout=180.0,
)
print("status", r.status_code)
d = r.json()
print("ms", d.get("processing_ms"), "form", d.get("form_type"))
f = d.get("fields", {})
for k in [
    "Year",
    "PAYER'S name, address, and telephone",
    "Payer's TIN",
    "Recipient's TIN",
    "Recipient's Name",
    "Recipient's Street Address (including apt. no.)",
    "Recipient's city, state, country and Zip code",
    "Account Number",
    "1 Interest Income",
    "2 Early withdrawal penalty",
    "4 Federal income tax withheld",
]:
    print(f"{k}: {f.get(k)}")
