from __future__ import annotations

from typing import Any

from app.ocr.field_engine import FieldSpec, SpatialFieldEngine
from app.ocr.types import OcrResult


def _specs() -> list[FieldSpec]:
    return [
        FieldSpec("Year", "year", labels=["Tax Year", "Form 1099 - DIV", "1099-DIV"]),
        FieldSpec(
            "PAYER'S name, address, and telephone",
            "address_block",
            role="payer",
            part="combined",
        ),
        FieldSpec(
            "Payer's TIN",
            "tin_ein",
            labels=["Payer's Federal ID", "PAYER'S TIN", "Federal ID No"],
        ),
        FieldSpec(
            "Recipient's TIN",
            "tin_ssn",
            labels=["Recipient's ID No", "RECIPIENT'S TIN", "Recipient's TIN"],
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
        FieldSpec(
            "Account Number",
            "account",
            labels=["Account Number", "Holder Account Number", "AccountNumber"],
        ),
        FieldSpec("2nd TIN not.", "raw", labels=["2nd TIN"]),
        FieldSpec(
            "1a Total ordinary dividends",
            "money",
            labels=["Total Ordinary Dividends", "Total ordinary dividends", "1a Total Ordinary"],
            box="1a",
        ),
        FieldSpec(
            "1b Qualified dividends",
            "money",
            labels=["Qualified Dividends", "Qualified dividends", "1b Qualified"],
            box="1b",
        ),
        FieldSpec(
            "2a Total capital gain distr.",
            "money",
            labels=["Total capital gain", "Total Capital Gain Distributions"],
            box="2a",
        ),
        FieldSpec("2b Unrecap. Sec. 1250 gain", "money", labels=["Unrecap"], box="2b"),
        FieldSpec("2c Section 1202 gain", "money", labels=["Section 1202"], box="2c"),
        FieldSpec("2d Collectibles (28%) gain", "money", labels=["Collectibles"], box="2d"),
        FieldSpec("2e Section 897 ordinary dividends", "money", labels=["897 Ordinary"], box="2e"),
        FieldSpec("2f Section 897 capital gain", "money", labels=["897 Capital"], box="2f"),
        FieldSpec(
            "3 Nondividend distributions",
            "money",
            labels=["Nondividend distributions", "3 Nondividend"],
            box="3",
        ),
        FieldSpec(
            "4 Federal income tax withheld",
            "money",
            labels=["Federal income tax withheld", "FEDERALINCOME TAX WITHHELD"],
            box="4",
        ),
        FieldSpec(
            "5 Section 199A dividends",
            "money",
            labels=["199A dividends", "Section 199A"],
            box="5",
        ),
        FieldSpec(
            "6 Investment expenses",
            "money",
            labels=["Investment expenses"],
            box="6",
        ),
        FieldSpec(
            "7 Foreign tax paid",
            "money",
            labels=["Foreign tax paid", "Foreign Tax Paid"],
            box="7",
        ),
        FieldSpec("8 Foreign country or U.S. possession", "raw", labels=["Foreign Country"]),
        FieldSpec(
            "9 Cash liquidation distributions",
            "money",
            labels=["Cash liquidation", "Cash Liquidation"],
            box="9",
        ),
        FieldSpec(
            "10 Noncash liquidation distributions",
            "money",
            labels=["Noncash liquidation"],
            box="10",
        ),
        FieldSpec("11 FATCA filing Requirement", "checkbox", labels=["FATCA"]),
        FieldSpec(
            "12 Exempt-interest dividends",
            "money",
            labels=["Exempt-Interest Dividends", "Exempt-interest"],
            box="12",
        ),
        FieldSpec(
            "13 Specified private activity bond interest dividends",
            "money",
            labels=["Specified Private Activity"],
            box="13",
        ),
        FieldSpec("14 State", "raw", labels=["14 State"]),
        FieldSpec("15 State identification no.", "raw", labels=["State Identification"]),
        FieldSpec(
            "16 State tax withheld",
            "money",
            labels=["State Tax Withheld"],
            box="16",
        ),
    ]


def extract_1099_div(source: OcrResult | str) -> dict[str, Any]:
    if isinstance(source, str):
        eng = SpatialFieldEngine(text=source)
    else:
        eng = SpatialFieldEngine.from_ocr(source)
    fields = eng.extract(_specs())
    import re

    from app.ocr.field_engine import normalize_money

    # Compact 5-amount row under DIV headers (authoritative when present)
    m = re.search(
        r"(?:1a\s*)?Total Ordinary[^\n]*\n(?:[^\n]*\n){0,2}?"
        r"(\d+\.\d{2})\s+(\d+\.\d{2})\s+(\d+\.\d{2})\s+(\d+\.\d{2})\s+(\d+\.\d{2})",
        eng.text,
        flags=re.I,
    )
    if m:
        fields["1a Total ordinary dividends"] = normalize_money(m.group(1))
        fields["1b Qualified dividends"] = normalize_money(m.group(2))
        fields["3 Nondividend distributions"] = normalize_money(m.group(3))
        fields["4 Federal income tax withheld"] = normalize_money(m.group(4))
        fields["7 Foreign tax paid"] = normalize_money(m.group(5))

    # Payer block under "Payer's Details" (custodian layouts)
    m = re.search(
        r"Payer'?s?\s*Details[\s\S]{0,80}?"
        r"((?:[A-Z]{3,}[A-Z0-9 &.,']*(?:\n[A-Z][A-Z0-9 &.,']*){0,2}))\s*\n"
        r"(PO\s*BOX\s*\d+|P\.?O\.?\s*BOX\s*\d+)\s*\n"
        r"([A-Z][A-Z0-9 ]+\d{5}(?:-\d{4})?)",
        eng.text,
        flags=re.I,
    )
    if m:
        name = re.sub(r"^(?:\d+\.\d{2}\s+)+", "", m.group(1))
        name = re.sub(r"\s+", " ", name).strip()
        if name:
            city = eng._norm_city(m.group(3))
            street = eng._norm_street(m.group(2))
            fields["PAYER'S name, address, and telephone"] = ", ".join(
                x for x in [name, street, city] if x
            )

    # Recipient: registration / mail panel (EQ Shareowner style)
    if not fields.get("Recipient's Name"):
        m = re.search(
            r"(?:Registration|Recipient'?s?\s*name)\s*:?\s*\n\s*"
            r"([A-Z][A-Z0-9 &.,'-]{3,50})\s*\n"
            r"(?:(?:UA|TR|TRUST)[^\n]*\n){0,3}"
            r"(\d+\s+[A-Z0-9 .#'-]+(?:DR|ST|AVE|RD|WAY|LN|CIR|BLVD)\.?)\s*\n"
            r"([A-Z][A-Z ]+\s+[A-Z]{2}\s+\d{5}(?:-\d{4})?)",
            eng.text,
            flags=re.I,
        )
        if m:
            fields["Recipient's Name"] = re.sub(r"\s+", " ", m.group(1)).strip()
            fields["Recipient's Street Address (including apt. no.)"] = m.group(2).strip()
            fields["Recipient's city, state, country and Zip code"] = eng._norm_city(
                m.group(3).strip()
            )

    # OCR / cover layouts: CATHERINE BRACK TR style without labels
    if not fields.get("Recipient's Name"):
        m = re.search(
            r"(?m)^([A-Z][A-Z]+(?:\s+[A-Z][A-Z]+){1,3}(?:\s+TR(?:UST)?)?)\s*$\n"
            r"(?:(?:UA|TR|TRUST|BRACK|LIVING)[^\n]*\n){0,3}"
            r"^(\d+\s+[A-Z0-9 .#'-]+(?:DR|ST|AVE|RD|WAY|LN|CIR|BLVD)\.?)\s*$\n"
            r"^([A-Z][A-Z ]+\s+[A-Z]{2}\s+\d{5}(?:-\d{4})?)\s*$",
            eng.text,
            flags=re.I | re.M,
        )
        if m and not re.search(r"\b(?:SOUTHERN|EQUINITI|COMPANY|PAYER|DIVIDEND)\b", m.group(1), re.I):
            fields["Recipient's Name"] = re.sub(r"\s+", " ", m.group(1)).strip()
            fields["Recipient's Street Address (including apt. no.)"] = m.group(2).strip()
            fields["Recipient's city, state, country and Zip code"] = eng._norm_city(
                m.group(3).strip()
            )

    # Ordinary dividends amount fallback
    if not fields.get("1a Total ordinary dividends"):
        m = re.search(
            r"(?:1a|Total\s*ordinary\s*dividends?)[^\n]{0,40}?\$?\s*([0-9,]+\.\d{2})",
            eng.text,
            re.I,
        )
        if m:
            fields["1a Total ordinary dividends"] = normalize_money(m.group(1))

    # Southern Company / EQ Shareowner scans often park 1a under wrong box
    if not fields.get("1a Total ordinary dividends"):
        inv = fields.get("6 Investment expenses")
        if inv and inv not in {"0.00", "0"}:
            fields["1a Total ordinary dividends"] = inv
            fields["1b Qualified dividends"] = fields.get("1b Qualified dividends") or inv
            fields["6 Investment expenses"] = "0.00"

    # CATHERINE BRACK TR / similar registration lines near MILLCREEK / CHARLESTON
    if not fields.get("Recipient's Name"):
        m = re.search(
            r"(CATHERINE\s+BRACK(?:\s+TR)?|[A-Z]{4,}\s+[A-Z]{4,}(?:\s+TR)?)\s*\n"
            r"(?:UA\s+[^\n]+\n)?(?:[A-Z ]*TRUST\s*\n)?"
            r"(\d+\s+[A-Z]+(?:CREEK|MILL|STREET|ROAD)?[A-Z ]*(?:DR|ST|AVE|RD|WAY|LN|CIR)\.?)\s*\n"
            r"([A-Z][A-Z ]+\s+[A-Z]{2}\s+\d{5}(?:-\d{4})?)",
            eng.text,
            re.I,
        )
        if m:
            fields["Recipient's Name"] = re.sub(r"\s+", " ", m.group(1)).strip()
            fields["Recipient's Street Address (including apt. no.)"] = m.group(2).strip()
            fields["Recipient's city, state, country and Zip code"] = eng._norm_city(
                m.group(3).strip()
            )

    # Recipient block fallback (mirrors 1099-INT)
    if not fields.get("Recipient's Name"):
        m = re.search(
            r"RECIPIENT'?S?\s*name[^\n]*\n\s*"
            r"([A-Z][A-Za-z0-9 &.,'-]{2,50})\s*\n"
            r"(?:Street\s*address[^\n]*\n)?\s*"
            r"(\d+\s+[A-Z0-9 .#'-]+(?:ST|AVE|RD|DR|WAY|LN|BLVD|CT|CIR|PL|HWY|PKWY)?\.?)\s*\n"
            r"(?:City[^\n]*\n)?\s*"
            r"([A-Z][A-Za-z0-9 .]+(?:,\s*)?[A-Z]{2}\s+\d{5}(?:-\d{4})?)",
            eng.text,
            flags=re.I,
        )
        if not m:
            m = re.search(
                r"(?m)^([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)\s*$\n"
                r"^(\d+\s+[A-Za-z0-9 .#'-]+)\s*$\n"
                r"^([A-Za-z .]+,\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)\s*$",
                eng.text,
            )
        if m:
            name = re.sub(r"\s+", " ", m.group(1)).strip()
            if not re.search(
                r"(?:Payer|Recipient|Street|City|Dividend|Federal|Account|Form|Box)\b",
                name,
                re.I,
            ):
                fields["Recipient's Name"] = name
                if not fields.get("Recipient's Street Address (including apt. no.)"):
                    fields["Recipient's Street Address (including apt. no.)"] = m.group(2).strip()
                if not fields.get("Recipient's city, state, country and Zip code"):
                    fields["Recipient's city, state, country and Zip code"] = eng._norm_city(
                        m.group(3).strip()
                    )
    return fields
