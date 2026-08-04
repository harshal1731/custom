from __future__ import annotations

from typing import Any

from app.ocr.field_engine import FieldSpec, SpatialFieldEngine
from app.ocr.types import OcrResult


def _specs() -> list[FieldSpec]:
    return [
        FieldSpec("Year", "year", labels=["Form W-2", "Wage and Tax Statement"]),
        FieldSpec(
            "Employee's social security number",
            "tin_ssn",
            labels=["Employee's social security number", "social security number"],
        ),
        FieldSpec(
            "Employer identification number (EIN)",
            "tin_ein",
            labels=["Employer ID number", "Employer identification number", "EIN"],
        ),
        FieldSpec(
            "Employer's name, address, and ZIP code",
            "address_block",
            role="employer",
            part="combined",
        ),
        FieldSpec("Control number", "raw", labels=["Control number"]),
        FieldSpec(
            "Employee's first name and initial",
            "name_split",
            role="employee",
            part="first",
        ),
        FieldSpec("Last name", "name_split", role="employee", part="last"),
        FieldSpec("Suff.", "raw", labels=["Suff"]),
        FieldSpec(
            "Employee's address and ZIP code",
            "address_block",
            role="employee",
            part="combined",
        ),
        FieldSpec(
            "1 Wages, tips, other compensation",
            "money",
            labels=["Wages, tips, other compensation"],
            box="1",
        ),
        FieldSpec(
            "2 Federal income tax withheld",
            "money",
            labels=["Federal income tax withheld"],
            box="2",
        ),
        FieldSpec(
            "3 Social security wages",
            "money",
            labels=["Social security wages"],
            box="3",
        ),
        FieldSpec(
            "4 Social security tax withheld",
            "money",
            labels=["Social security tax withheld"],
            box="4",
        ),
        FieldSpec(
            "5 Medicare wages and tips",
            "money",
            labels=["Medicare wages and tips"],
            box="5",
        ),
        FieldSpec(
            "6 Medicare tax withheld",
            "money",
            labels=["Medicare tax withheld"],
            box="6",
        ),
        FieldSpec("7 Social security tips", "money", labels=["Social security tips"], box="7"),
        FieldSpec("8 Allocated tips", "money", labels=["Allocated tips"], box="8"),
        FieldSpec(
            "10 Dependent care benefits",
            "money",
            labels=["Dependent care benefits"],
            box="10",
        ),
        FieldSpec("11 Nonqualified plans", "money", labels=["Nonqualified plans"], box="11"),
        FieldSpec("12a Code/Amount", "raw", labels=["12a"]),
        FieldSpec("12b Code/Amount", "raw", labels=["12b"]),
        FieldSpec("12c Code/Amount", "raw", labels=["12c"]),
        FieldSpec("12d Code/Amount", "raw", labels=["12d"]),
        FieldSpec("13 Statutory employee", "checkbox", labels=["Statutory employee"]),
        FieldSpec("13 Retirement plan", "checkbox", labels=["Retirement plan"]),
        FieldSpec("13 Third-party sick pay", "checkbox", labels=["Third-party sick pay"]),
        FieldSpec("14 Other", "raw", labels=["14 Other", "Other"]),
        FieldSpec(
            "15 State / Employer's state ID number",
            "raw",
            labels=["Employer's state ID number", "State Employer's state ID"],
        ),
        FieldSpec(
            "16 State wages, tips, etc.",
            "money",
            labels=["State wages, tips"],
            box="16",
        ),
        FieldSpec(
            "17 State income tax",
            "money",
            labels=["State income tax"],
            box="17",
        ),
        FieldSpec("18 Local wages, tips, etc.", "money", labels=["Local wages"], box="18"),
        FieldSpec("19 Local income tax", "money", labels=["Local income tax"], box="19"),
        FieldSpec("20 Locality name", "raw", labels=["Locality name"]),
    ]


def extract_w2(source: OcrResult | str) -> dict[str, Any]:
    import re
    from app.ocr.field_engine import normalize_money

    if isinstance(source, str):
        eng = SpatialFieldEngine(text=source)
        text = eng.text
    else:
        eng = SpatialFieldEngine.from_ocr(source, prefer_left_half=True)
        # Always keep full-page text available for regex fallbacks
        text = source.full_text or eng.text
    fields = eng.extract(_specs())

    # ---- Detect if the spatial engine extracted mostly garbage ----
    # Count how many "key" money fields have valid values
    key_money = ["1 Wages, tips, other compensation", "3 Social security wages",
                 "5 Medicare wages and tips"]
    filled_money = sum(1 for k in key_money
                       if fields.get(k) and re.search(r"\d+\.\d{2}$", str(fields[k])))

    # If left-half extraction got nothing useful, try full page
    if filled_money == 0 and not isinstance(source, str) and source.pages:
        eng_full = SpatialFieldEngine.from_ocr(source, prefer_left_half=False)
        fields_full = eng_full.extract(_specs())
        filled_full = sum(1 for k in key_money
                          if fields_full.get(k) and re.search(r"\d+\.\d{2}$", str(fields_full[k])))
        if filled_full > filled_money:
            fields = fields_full
            eng = eng_full

    # Prefer full-page text for regex recovery
    if not isinstance(source, str) and source.full_text:
        text = source.full_text

    # ---- No-space regex fallbacks for ALL important fields ----
    no_space = re.sub(r'\s+', '', eng.text)
    money_pat = r"((?:[1-9]\d{0,2}(?:,\d{3})*|\d+)\.\d{2})"

    # SSN Fallback (check both spaced and no-space)
    if not fields.get("Employee's social security number"):
        m = re.search(r"(?:X{3}|x{3}|\d{3})-(?:X{2}|x{2}|\d{2})-\d{4}", text)
        if m:
            fields["Employee's social security number"] = m.group(0)

    if not fields.get("Employee's social security number"):
        m = re.search(r"aEmployee.{0,40}?socialsecurity.*?(\d{3}-?\d{2}-?\d{4})", no_space, re.I)
        if m:
            d = re.sub(r"\D", "", m.group(1))
            if len(d) == 9:
                fields["Employee's social security number"] = f"{d[:3]}-{d[3:5]}-{d[5:]}"

    # EIN Fallback
    if not fields.get("Employer identification number (EIN)"):
        m = re.search(r"bEmployer(?:identificationnumber)?(?:\[EIN\]|\(EIN\))?.*?(\d{2}-?\d{7})", no_space, re.I)
        if m:
            d = re.sub(r"\D", "", m.group(1))
            if len(d) == 9:
                fields["Employer identification number (EIN)"] = f"{d[:2]}-{d[2:]}"

    # Money field fallbacks — search no_space text for label+amount
    _money_fallbacks = [
        ("1 Wages, tips, other compensation", r"1Wages(?:,tips,othercomp\.?)?.*?" + money_pat),
        ("2 Federal income tax withheld", r"2Federal(?:incometax)?withheld.*?" + money_pat),
        ("3 Social security wages", r"3Socialsecuritywages.*?" + money_pat),
        ("4 Social security tax withheld", r"4Socialsecuritytaxwithheld.*?" + money_pat),
        ("5 Medicare wages and tips", r"5Medicarewagesandtips.*?" + money_pat),
        ("6 Medicare tax withheld", r"6Medicaretaxwithheld.*?" + money_pat),
        ("11 Nonqualified plans", r"11Nonqualifiedplans.*?" + money_pat),
        ("16 State wages, tips, etc.", r"16Statewages(?:,tips,etc\.?)?.*?" + money_pat),
        ("17 State income tax", r"17Stateincometax.*?" + money_pat),
    ]
    for field_name, pattern in _money_fallbacks:
        if not fields.get(field_name):
            m = re.search(pattern, no_space, re.I)
            if m:
                fields[field_name] = normalize_money(m.group(1))

    # ---- Row-based patterns (image scans with tabular layout) ----
    ssn_row = re.search(
        r"((?:X{3}|x{3}|\d{3})-(?:X{2}|x{2}|\d{2})-\d{4})\s+"
        r"((?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})\s+"
        r"((?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})",
        text,
    )
    if ssn_row and not fields.get("1 Wages, tips, other compensation"):
        fields["Employee's social security number"] = ssn_row.group(1)
        fields["1 Wages, tips, other compensation"] = normalize_money(ssn_row.group(2))
        fields["2 Federal income tax withheld"] = normalize_money(ssn_row.group(3))

    ein_row = re.search(
        r"(\d{2}-\d{7})\s+((?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})\s*[;,]?\s*"
        r"((?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})",
        text,
    )
    if ein_row and not fields.get("3 Social security wages"):
        fields["Employer identification number (EIN)"] = ein_row.group(1)
        fields["3 Social security wages"] = normalize_money(ein_row.group(2))
        fields["4 Social security tax withheld"] = normalize_money(ein_row.group(3))

    ctrl_row = re.search(
        r"(\d{6,8}-\d)\s+((?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})\s+"
        r"((?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})",
        text,
    )
    if ctrl_row and not fields.get("5 Medicare wages and tips"):
        fields["Control number"] = ctrl_row.group(1)
        fields["5 Medicare wages and tips"] = normalize_money(ctrl_row.group(2))
        fields["6 Medicare tax withheld"] = normalize_money(ctrl_row.group(3))

    state_row = re.search(
        r"\b([A-Za-z]{2})\s+(\d[\d-]{4,})\s+"
        r"((?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})\s+"
        r"((?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})",
        text,
    )
    if state_row and not fields.get("16 State wages, tips, etc."):
        fields["15 State / Employer's state ID number"] = (
            f"{state_row.group(1).upper()} {state_row.group(2)}"
        )
        fields["16 State wages, tips, etc."] = normalize_money(state_row.group(3))
        fields["17 State income tax"] = normalize_money(state_row.group(4))

    # ---- State ID from no-space text ----
    if not fields.get("15 State / Employer's state ID number"):
        m = re.search(r"15State.*?Employer.*?stateIDno\.?.*?(\d{5,}-?\d+)", no_space, re.I)
        if m:
            fields["15 State / Employer's state ID number"] = m.group(1)

    # ---- Year from no-space ----
    if not fields.get("Year"):
        m = re.search(r"FormW-2.*?(20\d{2})", no_space, re.I)
        if m:
            fields["Year"] = m.group(1)
    if not fields.get("Year"):
        m = re.search(r"(20\d{2})", text)
        if m:
            fields["Year"] = m.group(1)

    # ---- Employee name/address ----
    emp = eng.find_party("employee")
    corp_emp = re.compile(
        r"\b(?:Inc|LLC|LLP|Corp|Company|Mortgage|Bank|Services|Hospital|Authority)\b",
        re.I,
    )

    def _set_employee_name(name: str) -> None:
        parts = [p for p in name.split() if re.search(r"[A-Za-z]", p)]
        if len(parts) >= 4 and len(parts) % 2 == 0:
            half = len(parts) // 2
            if [p.lower() for p in parts[:half]] == [p.lower() for p in parts[half:]]:
                parts = parts[:half]
        if len(parts) >= 2 and not corp_emp.search(name):
            fields["Employee's first name and initial"] = " ".join(parts[:-1])
            fields["Last name"] = parts[-1]

    if emp.get("street") or emp.get("city"):
        bits = [emp.get("street"), emp.get("city")]
        fields["Employee's address and ZIP code"] = ", ".join(b for b in bits if b)
    if emp.get("name") and not corp_emp.search(emp["name"]):
        _set_employee_name(emp["name"])

    # Prefer person line after box-e employee label (skip box 11/13 noise + employer)
    first = fields.get("Employee's first name and initial")
    last = fields.get("Last name")
    combined = f"{first or ''} {last or ''}".strip()
    if not first or corp_emp.search(combined):
        m = re.search(
            r"e\s*Employee'?s?\s*name[\s\S]{0,500}?"
            r"((?:[A-Z][a-z]+|[A-Z]{2,})(?:\s+[A-Z]\.?)?(?:\s+(?:[A-Z][a-z]+|[A-Z]{2,})){1,3})"
            r"\s+"
            r"(\d+\s+[A-Za-z0-9 .#'-]+)"
            r"\s+"
            r"([A-Za-z .]+,\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)",
            text,
            re.I,
        )
        if m and not corp_emp.search(m.group(1)) and not re.search(
            r"(?:Nonqualified|Statutory|Retirement|Third-party|Dependent|Employer|"
            r"Social\s*security|Medicare|Wages|Control|Sente|employee|sick\s*pay)",
            m.group(1),
            re.I,
        ):
            _set_employee_name(m.group(1).strip())
            fields["Employee's address and ZIP code"] = (
                f"{m.group(2).strip()}, {m.group(3).strip()}"
            )

    # Explicit Title-Case person + street + city anywhere on Copy B
    if not fields.get("Employee's first name and initial"):
        m = re.search(
            r"([A-Z][a-z]+\s+[A-Z]\.?\s+[A-Z][a-z]+)\s+"
            r"(\d+\s+[A-Za-z0-9 .#'-]+)\s+"
            r"([A-Za-z .]+,\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)",
            text,
        )
        if m and not corp_emp.search(m.group(1)):
            _set_employee_name(m.group(1))
            fields["Employee's address and ZIP code"] = (
                f"{m.group(2).strip()}, {m.group(3).strip()}"
            )

    # Browser title / header often has "First Last - ... - Employer"
    if not fields.get("Employee's first name and initial"):
        m = re.search(
            r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*-\s*\d+\s*-\s*",
            text,
            re.M,
        )
        if m and not corp_emp.search(m.group(1)):
            _set_employee_name(m.group(1))

    # ---- Employer name from no-space as fallback ----
    if not fields.get("Employer's name, address, and ZIP code"):
        m = re.search(
            r"cEmployer.{0,40}?name.*?ZIPcode\s*([A-Z][A-Z0-9 &.,']+(?:\n[A-Z0-9 &.,']+){0,2})",
            text,
            re.I,
        )
        if m:
            fields["Employer's name, address, and ZIP code"] = re.sub(r"\s+", " ", m.group(1)).strip()

    # ---- Validate: don't emit single-letter garbage from spaced PDFs ----
    for key in list(fields.keys()):
        val = fields[key]
        if isinstance(val, str) and len(val) == 1 and val.isalpha():
            # Single letter values are almost certainly OCR noise
            fields[key] = None

    return fields

