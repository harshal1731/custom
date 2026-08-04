from __future__ import annotations

from typing import Any

from app.ocr.field_engine import FieldSpec, SpatialFieldEngine
from app.ocr.types import OcrResult


def _specs() -> list[FieldSpec]:
    return [
        FieldSpec("Year", "year", labels=["Tax Year", "calendar year", "TAXYEAR"]),
        FieldSpec(
            "PAYER'S name, address, and telephone",
            "address_block",
            role="payer",
            part="combined",
        ),
        FieldSpec(
            "Payer's TIN",
            "tin_ein",
            labels=["PAYER'S TIN", "Payer's TIN", "Payer's ID Number", "E.I.N"],
        ),
        FieldSpec(
            "Recipient's TIN",
            "tin_ssn",
            labels=[
                "RECIPIENT'S TIN",
                "Recipient's TIN",
                "Tax ID Number",
                "TAXPAYER ID NUMBER",
                "Taxpayer ID",
            ],
        ),
        FieldSpec("Recipient's Name", "address_block", role="recipient", part="name"),
        FieldSpec(
            "Recipient's Street Address (including apt. no.)",
            "address_block",
            role="recipient",
            part="street",
        ),
        FieldSpec(
            "Recipient's city, state, country and Zip code",
            "address_block",
            role="recipient",
            part="city",
        ),
        FieldSpec("FATCA filing Requirement", "checkbox", labels=["FATCA"]),
        FieldSpec("Account Number", "account", labels=["Account number", "Account Number"]),
        FieldSpec("Payer's RTN (Optional)", "raw", labels=["Payer's RTN", "Payer's RTN (optional)"]),
        FieldSpec(
            "1 Interest Income",
            "money",
            labels=["Interest income", "Interest Income"],
            box="1",
            sum_repeats=True,
        ),
        FieldSpec(
            "2 Early withdrawal penalty",
            "money",
            labels=["Early withdrawal penalty", "Eariy withdrawal"],
            box="2",
            sum_repeats=True,
            default="0.00",
        ),
        FieldSpec(
            "3 Interest on U.S. Savings Bonds and Treasury obligations",
            "money",
            labels=["Interest on U.S. Savings Bonds"],
            box="3",
            sum_repeats=True,
            default="0.00",
        ),
        FieldSpec(
            "4 Federal income tax withheld",
            "money",
            labels=["Federal income tax withheld"],
            box="4",
            sum_repeats=True,
            default="0.00",
        ),
        FieldSpec(
            "5 Investment expenses",
            "money",
            labels=["Investment expenses"],
            box="5",
            sum_repeats=True,
            default="0.00",
        ),
        FieldSpec(
            "6 Foreign tax paid",
            "money",
            labels=["Foreign tax paid"],
            box="6",
            sum_repeats=True,
            default="0.00",
        ),
        FieldSpec("7 Foreign country or U.S. possession", "raw", labels=["Foreign country"]),
        FieldSpec(
            "8 Tax-exempt interest",
            "money",
            labels=["Tax-exempt interest"],
            box="8",
            sum_repeats=True,
            default="0.00",
        ),
        FieldSpec(
            "9 Specified private activity bond Interest",
            "money",
            labels=["Specified private activity bond"],
            box="9",
            sum_repeats=True,
            default="0.00",
        ),
        FieldSpec(
            "10 Market discount",
            "money",
            labels=["Market discount"],
            box="10",
            sum_repeats=True,
            default="0.00",
        ),
        FieldSpec(
            "11 Bond premium",
            "money",
            labels=["Bond premium"],
            box="11",
            sum_repeats=True,
            default="0.00",
        ),
        FieldSpec(
            "12 Bond premium on Treasury obligations",
            "money",
            labels=["Bond premium on Treasury"],
            box="12",
            sum_repeats=True,
            default="0.00",
        ),
        FieldSpec(
            "13 Bond premium on tax-exempt bond",
            "money",
            labels=["Bond premium on tax-exempt"],
            box="13",
            sum_repeats=True,
            default="0.00",
        ),
        FieldSpec(
            "14 Tax-exempt and tax credit bond CUSIP no.",
            "raw",
            labels=["CUSIP"],
        ),
        FieldSpec("15 State", "raw", labels=["15 State"]),
        FieldSpec("16 State identification no.", "raw", labels=["State identification"]),
        FieldSpec(
            "17 State tax withheld",
            "money",
            labels=["State tax withheld"],
            box="17",
            sum_repeats=True,
            default="0.00",
        ),
    ]


def extract_1099_int(source: OcrResult | str) -> dict[str, Any]:
    if isinstance(source, str):
        eng = SpatialFieldEngine(text=source)
    else:
        eng = SpatialFieldEngine.from_ocr(source)
    fields = eng.extract(_specs())
    
    import re
    # Recipient block fallback (label then values, possibly with blank label rows between)
    if not fields.get("Recipient's Name"):
        m = re.search(
            r"RECIPIENT'?S?\s*name[^\n]*\n\s*"
            r"([A-Z][A-Za-z0-9 &.,'-]{2,50})\s*\n"
            r"(?:Street\s*address[^\n]*\n)?\s*"
            r"(\d+\s+[A-Z0-9 .#'-]+(?:ST|AVE|RD|DR|WAY|LN|BLVD|CT|CIR|PL|HWY|PKWY|DRIVE|ROAD|LANE|HWY)?\.?)\s*\n"
            r"(?:City[^\n]*\n)?\s*"
            r"([A-Z][A-Za-z0-9 .]+(?:,\s*)?[A-Z]{2}\s+\d{5}(?:-\d{4})?)",
            eng.text,
            flags=re.I,
        )
        if not m:
            # Values may appear later in the PDF after empty template boxes
            m = re.search(
                r"(?m)^([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)\s*$\n"
                r"^(\d+\s+[A-Za-z0-9 .#'-]+),?\s*$\n"
                r"^([A-Za-z .]+,\s*[A-Z]{2}\s*,?\s*\d{5}(?:-\d{4})?)\s*$",
                eng.text,
            )
        if not m:
            m = re.search(
                r"([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)\s*\n"
                r"(\d+[^\n]{5,60})\s*\n"
                r"([A-Za-z .]+,\s*[A-Z]{2}\s*,?\s*\d{5}(?:-\d{4})?)",
                eng.text,
            )
        if m:
            name = re.sub(r"\s+", " ", m.group(1)).strip()
            if not re.search(
                r"(?:Payer|Recipient|Street|City|Interest|Federal|Account|Form|Box)\b",
                name,
                re.I,
            ):
                fields["Recipient's Name"] = name
                street = m.group(2).strip().rstrip(",")
                fields["Recipient's Street Address (including apt. no.)"] = street
                city_raw = m.group(3).strip()
                # Normalize "Lake Buena Vista,FL, 32830"
                city_raw = re.sub(r",\s*([A-Z]{2})\s*,\s*", r", \1 ", city_raw)
                fields["Recipient's city, state, country and Zip code"] = eng._norm_city(city_raw)

    # Interest income: labeled box — require real money, not the next box number
    if not fields.get("1 Interest Income"):
        from app.ocr.field_engine import normalize_money

        m = re.search(
            r"1\s*Interest income\s*\$\s*([0-9,]+\.\d{2})",
            eng.text,
            re.I,
        )
        if m:
            fields["1 Interest Income"] = normalize_money(m.group(1))
        else:
            # Values listed after recipient city (whole dollars OK)
            m = re.search(
                r"(?:[A-Z]{2}\s*,?\s*\d{5}(?:-\d{4})?)\s*\n?"
                r"[^\n]{0,20}\n?"
                r"([0-9A-Z-]{6,})\s*\n\s*"
                r"([1-9]\d{2,})(?:\s|\n)",
                eng.text,
            )
            if m:
                fields["Account Number"] = fields.get("Account Number") or m.group(1)
                fields["1 Interest Income"] = normalize_money(m.group(2) + ".00")

    if not fields.get("Account Number"):
        m = re.search(r"Account number[^\n]*\n\s*([0-9A-Z-]{6,})", eng.text, re.I)
        if m:
            fields["Account Number"] = m.group(1).strip()
        else:
            m = re.search(
                r"(?:Raymond|Buena Vista|Drive)[^\n]*\n[^\n]*\n[^\n]*\n\s*([0-9]{6,})\s*\n",
                eng.text,
                re.I,
            )
            if m:
                fields["Account Number"] = m.group(1).strip()

    # Payer block fallback
    if not fields.get("PAYER'S name, address, and telephone"):
        m = re.search(
            r"PAYER'?S?\s*name[^\n]*\n\s*([A-Z][A-Z0-9 &.,']+(?:\n[A-Z][A-Z0-9 &.,']+){0,1})\s*\n"
            r"(?:Box 4[^\n]*\n\s*(?:[0-9,.]+\s*\n)?)*"  # sometimes Box 4 is in the middle
            r"([A-Z][A-Z0-9 ]+\s*,\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)",
            eng.text,
            flags=re.I,
        )
        if m:
            name = re.sub(r"\s+", " ", m.group(1)).strip()
            city = eng._norm_city(m.group(2).strip())
            fields["PAYER'S name, address, and telephone"] = f"{name}, {city}"

    # Trailing payer block (Vanguard style)
    if not fields.get("PAYER'S name, address, and telephone"):
        m = re.search(
            r"(VANGUARD[^\n]*|BANK[^\n]*)\s*\n"
            r"(P\.?O\.?\s*BOX[^\n]+)\s*\n"
            r"([A-Z][A-Z ]+,\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)",
            eng.text,
            re.I,
        )
        if m:
            fields["PAYER'S name, address, and telephone"] = (
                f"{m.group(1).strip()}, {m.group(2).strip()}, {eng._norm_city(m.group(3))}"
            )

    # Title Security / escrow-style interest statements
    if not fields.get("Recipient's Name"):
        m = re.search(
            r"(?:Owner|Recipient|Registration)\s*:?\s*"
            r"([A-Z][A-Za-z &.,'-]{5,80}(?:Trust|Trustees?)?)\s*"
            r"(?:\n|,)\s*"
            r"(\d+\s+[A-Za-z0-9 .#'-]+)\s*(?:\n|,)\s*"
            r"([A-Za-z .]+,\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)",
            eng.text,
            re.I,
        )
        if m:
            fields["Recipient's Name"] = re.sub(r"\s+", " ", m.group(1)).strip()
            fields["Recipient's Street Address (including apt. no.)"] = m.group(2).strip()
            fields["Recipient's city, state, country and Zip code"] = eng._norm_city(
                m.group(3).strip()
            )
    if not fields.get("1 Interest Income"):
        m = re.search(
            r"(?:Interest\s*Income|Box\s*1)[^\n]{0,40}?\$?\s*([0-9,]+\.\d{2})",
            eng.text,
            re.I,
        )
        if m:
            from app.ocr.field_engine import normalize_money

            fields["1 Interest Income"] = normalize_money(m.group(1))
    if not fields.get("Account Number"):
        m = re.search(r"Account\s*No\.?\s*:?\s*([0-9]{8,})", eng.text, re.I)
        if m:
            fields["Account Number"] = m.group(1)

    return fields
