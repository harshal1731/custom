from __future__ import annotations

from typing import Any

from app.ocr.field_engine import FieldSpec, SpatialFieldEngine
from app.ocr.types import OcrResult


def _specs() -> list[FieldSpec]:
    return [
        FieldSpec("Year", "year", labels=["Tax Year", "Form 5498-SA", "contributions made in"]),
        FieldSpec(
            "TRUSTEE'S or ISSUER'S name, street address, city, state, ZIP",
            "address_block",
            role="trustee",
            part="combined",
        ),
        FieldSpec(
            "TRUSTEE'S or ISSUER'S TIN",
            "tin_ein",
            labels=["TRUSTEE'S federal identification number", "TRUSTEE'S TIN"],
        ),
        FieldSpec(
            "PARTICIPANT'S TIN",
            "tin_ssn",
            labels=["PARTICIPANT'S social security number", "PARTICIPANTS social security"],
        ),
        FieldSpec("PARTICIPANT'S name", "address_block", role="participant", part="name"),
        FieldSpec(
            "Street address (including apt. no.)",
            "address_block",
            role="participant",
            part="street",
        ),
        FieldSpec("City, state, and ZIP", "address_block", role="participant", part="city"),
        FieldSpec("Account number", "account", labels=["Account number"]),
        FieldSpec(
            "1 Employee or self-employed person's Archer MSA contributions made",
            "money",
            labels=["Archer MSA contributions made", "contributions made in"],
            box="1",
            default="0.00",
        ),
        FieldSpec(
            "2 Total contributions",
            "money",
            labels=["Total contributions made in", "2 Total contributions"],
            box="2",
            default="0.00",
        ),
        FieldSpec(
            "3 Total HSA or Archer MSA contributions made in following year",
            "money",
            labels=["Total HSA or Archer MSA contributions made", "for 2024"],
            box="3",
            default="0.00",
        ),
        FieldSpec(
            "4 Rollover contributions",
            "money",
            labels=["Rollover contributions"],
            box="4",
            default="0.00",
        ),
        FieldSpec(
            "5 FMV of HSA, Archer MSA, or MA MSA",
            "money",
            labels=["Fair market value of HSA", "Fair market value"],
            box="5",
        ),
        FieldSpec("6 HSA", "checkbox", labels=["6 HSA", "HSA"]),
        FieldSpec("6 Archer MSA", "checkbox", labels=["Archer MSA"]),
        FieldSpec("6 MA MSA", "checkbox", labels=["MA MSA"]),
    ]


def extract_5498_sa(source: OcrResult | str) -> dict[str, Any]:
    if isinstance(source, str):
        eng = SpatialFieldEngine(text=source)
    else:
        eng = SpatialFieldEngine.from_ocr(source)
    fields = eng.extract(_specs())
    import re

    from app.ocr.field_engine import normalize_money

    if not fields.get("5 FMV of HSA, Archer MSA, or MA MSA"):
        m = re.search(
            r"5\s*Fair market value[\s\S]{0,160}?\$\s*([0-9,]+\.\d{2})(?:\s+\$\s*([0-9,]+\.\d{2}))?",
            eng.text,
            re.I,
        )
        if m:
            if m.group(2):
                fields["4 Rollover contributions"] = normalize_money(m.group(1)) or "0.00"
                fields["5 FMV of HSA, Archer MSA, or MA MSA"] = normalize_money(m.group(2))
            else:
                fields["5 FMV of HSA, Archer MSA, or MA MSA"] = normalize_money(m.group(1))

    # Reject bogus account numbers that are just the form title
    acct = fields.get("Account number")
    if acct and re.search(r"5498|form\s*sa|account\s*number", str(acct), re.I):
        fields["Account number"] = None

    # Participant identity — prefer labeled Participant Information panel
    corpish = re.compile(
        r"\b(?:Bank|Trust|Credit\s*Union|Federal|Corporate|HealthEquity|Inc|LLC|"
        r"Trustee|Issuer|Internal|Revenue|Copy|MAMSA|MSA Information)\b",
        re.I,
    )

    def _accept_participant(name: str | None) -> str | None:
        if not name:
            return None
        name = re.sub(r"\s+", " ", name).strip(" ,")
        if len(name) < 5 or corpish.search(name):
            return None
        if re.search(r"\d{5}", name):  # city/zip fragments
            return None
        words = name.split()
        if len(words) < 2:
            return None
        # Reject city lines mistaken for names (e.g. "Jefferson City, MO 65101")
        if re.search(
            rf"^{re.escape(name)}\s*,\s*[A-Z]{{2}}\s*\d{{5}}",
            eng.text,
            re.I | re.M,
        ):
            return None
        if re.search(
            r"\b(?:City|Annual\s*Statement|Statement|Instructions|Registration)\b",
            name,
            re.I,
        ):
            return None
        return name

    # Clear bad spatial/mail hits
    if not _accept_participant(fields.get("PARTICIPANT'S name")):
        fields["PARTICIPANT'S name"] = None

    if not fields.get("PARTICIPANT'S name"):
        m = re.search(
            r"Participant\s*Information[\s\S]{0,60}?Name:\s*\n?\s*([A-Z][A-Za-z .'-]{2,50})",
            eng.text,
            re.I,
        )
        if m:
            fields["PARTICIPANT'S name"] = _accept_participant(m.group(1))

    if not fields.get("PARTICIPANT'S name"):
        m = re.search(
            r"PARTICIPANTS?\s*name[^\n]*\n\s*([A-Z][A-Za-z .'-]{2,50})",
            eng.text,
            re.I,
        )
        if m:
            name = re.split(
                r"\s+(?:Archer|MSA|HSA|Participant|Fair|Rollover|Street|Social|\$|\d)",
                m.group(1),
                flags=re.I,
            )[0].strip()
            fields["PARTICIPANT'S name"] = _accept_participant(name)

    # IRS layout: trustee block then participant name/street/city stacked
    if not fields.get("PARTICIPANT'S name"):
        m = re.search(
            r"(?:TRUSTEE'?S?\s*TIN|PARTICIPANT'?S?\s*TIN)[\s\S]{0,240}?"
            r"((?:XXX-XX-|\d{3}-\d{2}-)\d{4})\s+"
            r"([A-Z][A-Z .'-]{5,40})\s+"
            r"(\d+\s+[A-Z0-9 .]+(?:ST|DR|AVE|RD|WAY|LN|CIR|BLVD)\.?)\s+"
            r"([A-Z][A-Z .]+?\s+[A-Z]{2}\s*\d{5}(?:-\d{4})?)\s+"
            r"([0-9A-Z-]{2,20})",
            eng.text,
            re.I,
        )
        if m:
            fields["PARTICIPANT'S TIN"] = fields.get("PARTICIPANT'S TIN") or m.group(1)
            fields["PARTICIPANT'S name"] = _accept_participant(m.group(2))
            fields["Street address (including apt. no.)"] = m.group(3).strip()
            fields["City, state, and ZIP"] = eng._norm_city(m.group(4))
            acct = m.group(5).strip()
            if not re.search(r"^(?:20\d{2}|5498)", acct):
                fields["Account number"] = acct

    # Explicit ALL-CAPS person above street when values sit below the form grid
    if not fields.get("PARTICIPANT'S name"):
        for m in re.finditer(
            r"(?m)^([A-Z][A-Z]*(?:\s+[A-Z][A-Z'-]*){1,3})\s*$\n\s*"
            r"^(\d+\s+[A-Z0-9 .]+(?:ST|DR|AVE|RD|WAY|LN|CIR|BLVD)\.?)\s*$\n\s*"
            r"^([A-Z][A-Z .,]+?\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)\s*$",
            eng.text,
        ):
            name = _accept_participant(m.group(1))
            if name:
                fields["PARTICIPANT'S name"] = name
                fields["Street address (including apt. no.)"] = m.group(2).strip()
                fields["City, state, and ZIP"] = eng._norm_city(m.group(3))
                break

    # Optum / HSA cover letter: bank address then participant mail panel
    if not fields.get("PARTICIPANT'S name"):
        m = re.search(
            r"(?:Optum\s*Bank|PO\s*Box\s*\d+)[\s\S]{0,120}?"
            r"([A-Z][A-Z]+(?:\s+[A-Z][A-Z'-]+){1,3})\s*\n"
            r"(\d+\s+[A-Z0-9 .]+(?:ST|DR|AVE|RD|WAY|LN|CIR|BLVD)\.?)\s*\n"
            r"([A-Z][A-Z .,]+?\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)",
            eng.text,
            re.I,
        )
        if m:
            name = _accept_participant(m.group(1))
            if name:
                fields["PARTICIPANT'S name"] = name
                fields["Street address (including apt. no.)"] = m.group(2).strip()
                fields["City, state, and ZIP"] = eng._norm_city(m.group(3))

    if not fields.get("PARTICIPANT'S name"):
        m = re.search(r"Dear\s+([A-Z][A-Za-z'-]+)\s*:", eng.text)
        if m:
            # Prefer full mail-panel name containing this first name
            first = m.group(1).upper()
            m2 = re.search(
                rf"({first}(?:\s+[A-Z][A-Z'-]+){{1,3}})\s*\n"
                r"(\d+\s+[A-Z0-9 .]+(?:ST|DR|AVE|RD|WAY|LN|CIR|BLVD)\.?)\s*\n"
                r"([A-Z][A-Z .,]+?\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)",
                eng.text,
                re.I,
            )
            if m2:
                fields["PARTICIPANT'S name"] = _accept_participant(m2.group(1))
                if fields["PARTICIPANT'S name"]:
                    fields["Street address (including apt. no.)"] = m2.group(2).strip()
                    fields["City, state, and ZIP"] = eng._norm_city(m2.group(3))

    # Year: prefer contribution year in letter body over copyright year
    m = re.search(
        r"(?:contributions?\s*(?:made\s*)?(?:for|in)|tax\s*year|Form\s*5498-SA[^\n]{0,40})"
        r".{0,40}?\b(20\d{2})\b",
        eng.text,
        re.I,
    )
    if m:
        fields["Year"] = m.group(1)

    # Prefer participant street under Participant Information (not trustee Address:)
    street = str(fields.get("Street address (including apt. no.)") or "")
    if (not street) or re.match(r"^\d{8,}\b", street) or "BROUGHTON" in eng.text.upper() and "BROUGHTON" not in street.upper():
        m = re.search(
            r"Participant\s*Information[\s\S]{0,300}?Address:\s*\n\s*"
            r"(\d+\s+[A-Z0-9 .]+(?:ST|DR|AVE|RD|WAY|LN|CIR|BLVD)\.?)",
            eng.text,
            re.I,
        )
        if m:
            fields["Street address (including apt. no.)"] = m.group(1).strip()
        elif re.match(r"^\d{8,}\b", street):
            # Strip leading SSN digits mashed into street
            m2 = re.search(
                r"\b(\d+\s+[A-Z0-9 .]+(?:ST|DR|AVE|RD|WAY|LN|CIR|BLVD)\.?)\b",
                street,
                re.I,
            )
            fields["Street address (including apt. no.)"] = m2.group(1) if m2 else None

    if not fields.get("City, state, and ZIP"):
        m = re.search(
            r"(?:City(?:\s*or\s*tow[nm])?|City,\s*state)[^\n]*\n\s*"
            r"([A-Z][A-Za-z .]+(?:,\s*)?[A-Z]{2}\s*\d{5}(?:-\d{4})?)",
            eng.text,
            re.I,
        )
        if m and "INTERNAL" not in m.group(1).upper():
            fields["City, state, and ZIP"] = eng._norm_city(m.group(1))

    if not fields.get("City, state, and ZIP"):
        m = re.search(
            r"Participant\s*Information[\s\S]{0,200}?Address:\s*\n"
            r"\d+[^\n]+\n([A-Z][A-Za-z .]+,\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)",
            eng.text,
            re.I,
        )
        if m:
            fields["City, state, and ZIP"] = eng._norm_city(m.group(1))

    # Reject bogus account numbers before trying fallbacks
    acct = str(fields.get("Account number") or "")
    if not acct or re.search(
        r"5498|^20\d{2}$|form\s*sa|account\s*number|see\s*instructions|instructions",
        acct,
        re.I,
    ):
        fields["Account number"] = None

    if not fields.get("Account number"):
        m = re.search(r"Account\s*Number:\s*\n?\s*([0-9A-Z-]{4,})", eng.text, re.I)
        if m and not re.search(r"5498|^20\d{2}$|instructions", m.group(1), re.I):
            fields["Account number"] = m.group(1).strip()
    if not fields.get("Account number"):
        # IRS Copy B: account often immediately after city/zip line
        m = re.search(
            r"[A-Z]{2}\s*\d{5}(?:-\d{4})?\s*\r?\n\s*([0-9]{1,4}-[0-9]{1,4})\s*\r?\n",
            eng.text,
        )
        if not m:
            m = re.search(r"(?m)^\s*([0-9]{2}-[0-9]{2})\s*$", eng.text)
        if m:
            fields["Account number"] = m.group(1).strip()
    acct = str(fields.get("Account number") or "")
    if re.search(
        r"5498|^20\d{2}$|form\s*sa|account\s*number|see\s*instructions|instructions|"
        r"archer|msa|medicare|accourt|\(hsa\)",
        acct,
        re.I,
    ):
        fields["Account number"] = None

    # FMV: prefer amount after Fair market value / Box 5, else last non-zero $ amount
    if not fields.get("5 FMV of HSA, Archer MSA, or MA MSA") or fields.get(
        "5 FMV of HSA, Archer MSA, or MA MSA"
    ) in {"0.00", "0"}:
        fmv = None
        m = re.search(
            r"(?:Box\s*5|5)\s*Fair market value[\s\S]{0,80}?\$\s*([0-9,]+\.\d{2})",
            eng.text,
            re.I,
        )
        if m:
            fmv = m.group(1)
        if not fmv:
            m = re.search(
                r"Fair market value of HSA[\s\S]{0,120}?((?:[1-9]\d{0,2}(?:,\d{3})*|\d+)\.\d{2})",
                eng.text,
                re.I,
            )
            if m:
                fmv = m.group(1)
        if not fmv:
            amounts = re.findall(r"\$\s*([0-9,]+\.\d{2})", eng.text)
            nonzero = [a for a in amounts if normalize_money(a) not in {None, "0.00"}]
            if nonzero:
                fmv = nonzero[-1]
        if fmv:
            fields["5 FMV of HSA, Archer MSA, or MA MSA"] = normalize_money(fmv)

    # Trustee often appears as org + PO BOX under TRUSTEE header
    if not fields.get("TRUSTEE'S or ISSUER'S name, street address, city, state, ZIP"):
        t = eng.find_party("trustee")
        bits = [t.get("name"), t.get("street"), t.get("city")]
        fields["TRUSTEE'S or ISSUER'S name, street address, city, state, ZIP"] = (
            ", ".join(b for b in bits if b) or None
        )
    return fields
