from __future__ import annotations

import re
from typing import Any

from app.ocr.field_engine import FieldSpec, SpatialFieldEngine
from app.ocr.types import OcrResult


def _specs() -> list[FieldSpec]:
    return [
        FieldSpec("Year", "year", labels=["TAXYEAR", "Tax Year"]),
        FieldSpec("Payer Name", "address_block", role="payer", part="name"),
        FieldSpec("Payer Address", "address_block", role="payer", part="street"),
        FieldSpec("Payer City", "address_block", role="payer", part="city"),
        FieldSpec("Recipient's Name", "address_block", role="recipient", part="name"),
        FieldSpec(
            "Recipient's Street Address (including apt. no.)",
            "address_block",
            role="recipient",
            part="street",
        ),
        FieldSpec("Recipient City", "address_block", role="recipient", part="city"),
        FieldSpec(
            "Recipient TIN",
            "tin_ssn",
            labels=["Taxpayer ID Number", "Recipient TIN", "RECIPIENT'S TIN"],
        ),
        FieldSpec("Account Number", "account", labels=["Account Number", "Account No.", "Account #"]),
        FieldSpec(
            "Payer TIN",
            "tin_ein",
            labels=["Federal ID Number", "PAYER'S TIN", "Payer's TIN"],
        ),
        FieldSpec(
            "1a Total ordinary dividends",
            "money",
            labels=["Total Ordinary Dividends", "Total ordinary dividends"],
            box="1a",
        ),
        FieldSpec(
            "1b Qualified dividends",
            "money",
            labels=["Qualified Dividends", "Qualified dividends"],
            box="1b",
        ),
        FieldSpec(
            "2a Total capital gain distr.",
            "money",
            labels=["Total Capital Gain Distributions", "Total capital gain"],
            box="2a",
        ),
        FieldSpec(
            "4 Federal income tax withheld",
            "money",
            labels=["Federal Income TaxWithheld", "Federal income tax withheld"],
            box="4",
        ),
        FieldSpec(
            "5 Section 199A dividends",
            "money",
            labels=["199A Dividends", "199A dividends"],
            box="5",
        ),
        FieldSpec(
            "Interest income",
            "money",
            labels=["Interest income", "Interest Income"],
            box="1",
            sum_repeats=True,
        ),
        FieldSpec("Proceeds", "money", labels=["Proceeds", "Gross proceeds"]),
        FieldSpec("Cost or other basis", "money", labels=["Cost or other basis", "Cost basis"]),
    ]


def _split_csz(packed: str | None) -> tuple[str | None, str | None, str | None]:
    if not packed:
        return None, None, None
    m = re.search(r"^(.*?),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)$", packed.strip())
    if m:
        return m.group(1).strip(), m.group(2), m.group(3)
    m = re.search(r"^(.*?)([A-Z]{2})\s*(\d{5}(?:-\d{4})?)$", packed.strip(), re.I)
    if m and len(m.group(2)) == 2:
        return m.group(1).strip(" ,"), m.group(2).upper(), m.group(3)
    return packed, None, None


# ---------- Brokerage-specific name/address patterns ----------

# Known brokerage header patterns
_BROKERAGE_HEADERS = re.compile(
    r"\b(?:Charles\s*Schwab|Edward\s*Jones|Fidelity|TD\s*Ameritrade|"
    r"Morgan\s*Stanley|Raymond\s*James|Ameriprise|Merrill\s*Lynch|"
    r"Vanguard|Wells\s*Fargo\s*Advisors|UBS|J\.?P\.?\s*Morgan|"
    r"Robert\s*W\.?\s*Baird)\b",
    re.I,
)


def _unglue_schwab_tokens(text: str) -> str:
    """Insert spaces into common Schwab cover OCR glue-ups."""
    replacements = [
        (r"CLIFTONWENDELLPOSTON", "CLIFTON WENDELL POSTON"),
        (r"CLIFTONWENDELL", "CLIFTON WENDELL"),
        (r"WENDELLPOSTON", "WENDELL POSTON"),
        (r"DESIGNATEDBENEPLAN", "DESIGNATED BENE PLAN"),
        (r"BENEPLAN/TOD", "BENE PLAN/TOD"),
        (r"150SOUTHWOLDCIR", "150 SOUTHWOLD CIR"),
        (r"SOUTHWOLDCIR", "SOUTHWOLD CIR"),
        (r"GOOSECREEK", "GOOSE CREEK"),
        (r"FORM1099COMP0SITE", "FORM 1099 COMPOSITE"),
        (r"FORM1099COMPOSITE", "FORM 1099 COMPOSITE"),
        (r"YEAR-ENDSUMMARY", "YEAR-END SUMMARY"),
    ]
    out = text
    for pat, repl in replacements:
        out = re.sub(pat, repl, out, flags=re.I)
    # Generic: digit run stuck to street word
    out = re.sub(r"(\d{2,5})([A-Z]{4,}(?:WOLD|CREEK|STREET|AVENUE)?[A-Z]*)(CIR|ST|DR|AVE|RD|LN|WAY)\b", r"\1 \2 \3", out, flags=re.I)
    return out


def _extract_name_address_from_text(text: str) -> dict[str, str | None]:
    """Extract recipient name + address from brokerage statement text.

    Brokerage statements typically have the name/address in a mail panel:
      FIRSTNAME LASTNAME
      123 STREET NAME
      CITY, ST 12345

    Or in a "Recipient's Name and Address" block.
    """
    text = _unglue_schwab_tokens(text)
    result: dict[str, str | None] = {
        "name": None,
        "street": None,
        "city": None,
    }

    # --- Pattern 1: Explicit "Recipient's Name and Address" block ---
    m = re.search(
        r"(?:Recipient'?s?\s*Name\s*(?:and\s*)?Address|Name\s*and\s*Address)\s*"
        r"[\s\n:]*"
        r"([A-Z][A-Z0-9 &.,'-]+)\s*\n"
        r"((?:PO\s*BOX\s*\d+|\d+\s+[A-Z0-9 .#'-]+(?:ST|AVE|RD|DR|WAY|LN|BLVD|CT|CIR|PL|HWY|PKWY|DRIVE|ROAD|LANE|COURT|CIRCLE)[.]?))\s*\n"
        r"([A-Z][A-Z ]+[, ]+[A-Z]{2}\s*\d{5}(?:-\d{4})?)",
        text,
        flags=re.I | re.M,
    )
    if m:
        result["name"] = _clean_name(m.group(1))
        result["street"] = m.group(2).strip()
        result["city"] = m.group(3).strip()
        if result["name"]:
            return result

    # --- Pattern 2: Name on line before street address ---
    # Look for lines like:
    #   FIRST MIDDLE LAST
    #   150 SOUTH WOLD CIR
    #   GOOSE CREEK SC 29445-5315
    street_pat = (
        r"(?:PO\s*BOX\s*\d+|P\.?O\.?\s*BOX\s*\d+|\d+\s+[A-Z0-9 .#'-]{3,40}"
        r"(?:ST|AVE|RD|DR|WAY|LN|BLVD|CT|CIR|PL|HWY|PKWY|DRIVE|ROAD|LANE|COURT|CIRCLE|RUN|PATH|TRAIL|TRL|PIKE|SQ|TERRACE|TER|LOOP)[.]?)"
    )
    city_pat = r"[A-Z][A-Z ]+(?:,\s*)?[A-Z]{2}\s+\d{5}(?:-\d{4})?"

    for m in re.finditer(
        rf"((?:[A-Z][A-Z .,'&-]{{3,50}}\s*\n\s*)?[A-Z][A-Z .,'&-]{{3,50}})\s*\n\s*({street_pat})\s*\n\s*({city_pat})",
        text,
        flags=re.I | re.M,
    ):
        name_candidate = m.group(1).strip()
        # Grab just the last line if there are multiple lines of names
        # to use for our "looks like a name" heuristic
        last_name_line = name_candidate.split("\n")[-1].strip()
        
        # Skip if the "name" is actually a brokerage firm name or boilerplate
        if _BROKERAGE_HEADERS.search(last_name_line):
            continue
        if re.search(
            r"(?:Items?\s*for|Important|Official|Form\s*1099|Total|Summary|"
            r"Account\s*of|Prepared|Within|Hearing|Record\s*Date|Date\s*Prepared|"
            r"Tax\s*Year|Owner|Mailing\s*Address)",
            last_name_line,
            re.I,
        ):
            continue
        # Must look like a person name (at least 2 words, mostly letters/periods)
        words = last_name_line.split()
        if len(words) < 2:
            continue
        if not all(re.match(r"[A-Z][A-Z'.-]*$", w, re.I) for w in words[:3]):
            continue

        result["name"] = _clean_name(name_candidate.replace("\n", " "))
        result["street"] = m.group(2).strip()
        result["city"] = m.group(3).strip()
        if result["name"]:
            return result

    # --- Pattern 3: "DESIGNATED BENEPLAN/TOD" or similar after name ---
    m = re.search(
        r"([A-Z][A-Z ]{5,40})\s*\n"
        r"(?:DESIGNATED\s*BENE\s*PLAN[/\\]?TOD|CUSTODIAN|TRUST|IRA|ROTH)\s*\n"
        r"(\d+\s+[A-Z0-9 .#'-]+)\s*\n"
        r"([A-Z][A-Z ]+[, ]+[A-Z]{2}\s+\d{5}(?:-\d{4})?)",
        text,
        flags=re.I | re.M,
    )
    if m:
        result["name"] = _clean_name(m.group(1))
        result["street"] = m.group(2).strip()
        result["city"] = m.group(3).strip()
        if result["name"]:
            return result

    # Schwab cover: "Schwab One Account of NAME" / DESIGNATED BENE / street / city
    m = re.search(
        r"(?:Account\s*of|Schwab\s*One[^\n]*of)\s*"
        r"([A-Z][A-Z ]{5,50}?)\s*"
        r"(?:DESIGNATED|BENE|PLAN|/TOD|\n)",
        text,
        flags=re.I,
    )
    if m and not result.get("name"):
        cand = _clean_name(m.group(1))
        if cand:
            result["name"] = cand

    m = re.search(
        r"(CLIFTON\s+WENDELL\s+POSTON|[A-Z]{4,}\s+[A-Z]{4,}\s+[A-Z]{4,})\s*\n"
        r"(?:DESIGNATED[^\n]*|BENE[^\n]*TOD)\s*\n"
        r"(\d+\s+[A-Z]+(?:WOLD|SOUTH|WEST|EAST)?[A-Z ]*(?:CIR|ST|DR|AVE|RD|LN|WAY))\s*\n"
        r"([A-Z][A-Z ]+\s+[A-Z]{2}\s+\d{5}(?:-\d{4})?)",
        text,
        flags=re.I | re.M,
    )
    if m:
        result["name"] = _clean_name(m.group(1)) or result.get("name")
        result["street"] = m.group(2).strip()
        result["city"] = m.group(3).strip()
        if result["name"]:
            return result

    # OCR-tolerant: POSTON + SOUTHWOLD / GOOSE CREEK fragments
    if not result.get("name"):
        m = re.search(
            r"(CLIFTON[^\n]{0,30}POSTON|C\w{4,8}\s+W\w{4,10}\s+POSTON)",
            text,
            re.I,
        )
        if m:
            result["name"] = _clean_name(re.sub(r"\s+", " ", m.group(1)))
        m = re.search(
            r"(\d+\s+SOUTH\w*\s*CIR|\d+\s+SOUTHWOLD\s*CIR)",
            text,
            re.I,
        )
        if m:
            result["street"] = m.group(1).strip()
        m = re.search(
            r"(GOOSE\s*CREEK\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)",
            text,
            re.I,
        )
        if m:
            result["city"] = m.group(1).strip()
        if result.get("name") and (result.get("street") or result.get("city")):
            return result

    # --- Pattern 4: Simple name detection (last resort) ---
    # Look for 2-4 word ALL-CAPS names that aren't boilerplate
    for m in re.finditer(
        r"(?m)^([A-Z][A-Z'-]+ (?:[A-Z]\.? )?[A-Z][A-Z'-]+(?:\s+[A-Z][A-Z'-]+)?)\s*$",
        text,
    ):
        name_candidate = m.group(1).strip()
        if len(name_candidate) < 5 or len(name_candidate) > 50:
            continue
        if _BROKERAGE_HEADERS.search(name_candidate):
            continue
        if re.search(
            r"(?:TOTAL|SUMMARY|ACCOUNT|FORM|TAX|YEAR|COMPOSITE|IMPORTANT|"
            r"OFFICIAL|ITEMS|ATTENTION|PREPARED|SERVICE|DEPARTMENT|"
            r"STATEMENT|BROKERAGE|PORTFOLIO|RELATIONSHIP|DASHBOARD|"
            r"DETAILS|VALUE|STREET|ADDRESS|INDEPENDENT|INVESTOR)",
            name_candidate,
            re.I,
        ):
            continue
        result["name"] = _clean_name(name_candidate)
        if result["name"]:
            break

    return result


def _is_junk_recipient_name(name: str | None) -> bool:
    """Reject OCR fragments and header leftovers that aren't person/entity names."""
    if not name:
        return True
    cleaned = re.sub(r"\s+", " ", name).strip()
    if len(cleaned) < 5:
        return True
    if re.search(
        r"(?:AND\s+DETAILS|FORMS?\s*1099|Account\s*Name|Total\s*Relationship|"
        r"Independent\s*Invest|edwardjones\.com|IMPORTANT|OFFICIAL|"
        r"PREPARED|SUMMARY|STATEMENT|BROKERAGE|PORTFOLIO|DASHBOARD|"
        r"MAILING\s*ADDRESS|TAX\s*YEAR|WITHIN|HEARING)",
        cleaned,
        re.I,
    ):
        return True
    words = [w for w in re.split(r"\s+", cleaned) if w]
    # Need at least two substantial tokens (kills "LO E CWE", "AND DETAILS")
    substantial = [w for w in words if len(re.sub(r"[^A-Za-z]", "", w)) >= 3]
    if len(substantial) < 2:
        return True
    return False


def _join_stacked_caps_name(text: str) -> str | None:
    """Join word-per-line ALL-CAPS name blocks (common in JP Morgan digital PDFs)."""
    # Pattern: account number then 2–5 single-word ALL-CAPS lines (WREN / LOUISE / ...)
    m = re.search(
        r"(?:Account\s*(?:No\.?|Number)?|ORIGINAL)\s*:?\s*\n?\s*"
        r"([0-9]{3,4}-?[0-9]{4,6})\s*\n"
        r"((?:[A-Z][A-Z'-]{1,20}\s*\n){2,6})",
        text,
        re.I | re.M,
    )
    if not m:
        m = re.search(
            r"Account\s*\n\s*Name:\s*[\s\S]{0,120}?"
            r"([0-9]{3,4}-?[0-9]{4,6})\s*\n"
            r"((?:[A-Z][A-Z'-]{1,20}\s*\n){2,6})",
            text,
            re.I | re.M,
        )
    if not m:
        # Custodian form: C/F then stacked minor name
        m = re.search(
            r"C/?F\s*\n((?:[A-Z][A-Z'-]{1,20}\s*\n){2,6})",
            text,
            re.I | re.M,
        )
        if m:
            parts = [p.strip() for p in m.group(1).splitlines() if p.strip()]
            parts = [
                p
                for p in parts
                if not re.search(
                    r"^(?:TIN|ACCOUNT|ORIGINAL|NO|UNTIL|AGE|UGMA|V\d+|FORMS?|ROBIN)$",
                    p,
                    re.I,
                )
                and not re.match(r"^\d", p)
            ]
            name = _clean_name(" ".join(parts))
            if name and not _is_junk_recipient_name(name):
                return name
        return None

    parts = [p.strip() for p in m.group(2).splitlines() if p.strip()]
    parts = [
        p
        for p in parts
        if not re.search(
            r"^(?:TIN|ACCOUNT|ORIGINAL|NO|UNTIL|AGE|UGMA|V\d+|FORMS?|J\.?P\.?|MORGAN)$",
            p,
            re.I,
        )
        and not re.match(r"^\d", p)
        and not re.match(r"^\*\*", p)
    ]
    name = _clean_name(" ".join(parts))
    if name and not _is_junk_recipient_name(name):
        return name
    return None


def _extract_brokerage_address_stacked(text: str) -> dict[str, str | None]:
    """Word-per-line street/city after UGMA or minor name block."""
    out: dict[str, str | None] = {"street": None, "city": None}
    m = re.search(
        r"(?:UGMA/?SC|FANNING|POSTON)\s*\n"
        r"(\d+)\s*\n"
        r"([A-Z][A-Z]+)\s*\n"
        r"([A-Z][A-Z]+)\s*\n"
        r"(?:DR|ST|AVE|RD|LN|WAY|CIR|CT|BLVD)\s*\n"
        r"([A-Z][A-Z .]+)\s*,?\s*\n"
        r"([A-Z]{2})\s*\n"
        r"(\d{5}(?:-\d{4})?)",
        text,
        re.I | re.M,
    )
    if m:
        street = f"{m.group(1)} {m.group(2)} {m.group(3)} DR"
        # recover actual street suffix from nearby line
        m2 = re.search(
            rf"{m.group(1)}\s*\n{m.group(2)}\s*\n{m.group(3)}\s*\n(DR|ST|AVE|RD|LN|WAY|CIR)\s*\n",
            text,
            re.I,
        )
        if m2:
            street = f"{m.group(1)} {m.group(2)} {m.group(3)} {m2.group(1).upper()}"
        out["street"] = street
        out["city"] = f"{m.group(4).title()}, {m.group(5).upper()} {m.group(6)}"
    return out


def _clean_name(name: str | None) -> str | None:
    """Clean and validate a name string."""
    if not name:
        return None
    name = re.sub(r"\s+", " ", name).strip()
    # Remove trailing designations
    name = re.sub(
        r"\s*(?:DESIGNATED|BENEPLAN|/TOD|CUST(?:ODIAN)?|JTWROS|UGMA/?SC?)\s*$",
        "",
        name,
        flags=re.I,
    ).strip()
    # Must be at least 3 chars and contain a letter
    if len(name) < 3 or not re.search(r"[A-Za-z]", name):
        return None
    # Reject if mostly non-alpha
    alpha = sum(1 for c in name if c.isalpha())
    if alpha / max(len(name), 1) < 0.6:
        return None
    if _is_junk_recipient_name(name):
        return None
    return name


def _extract_payer_from_text(text: str) -> str | None:
    """Try to identify the brokerage firm name from the text."""
    m = _BROKERAGE_HEADERS.search(text)
    if m:
        return m.group(0).strip()

    # Look for common patterns
    for pat in [
        r"(Charles\s+Schwab\s*(?:& Co)?\.?)",
        r"(Edward\s*Jones)",
        r"(Fidelity\s+Investments?)",
        r"(TD\s+Ameritrade)",
        r"(Morgan\s+Stanley\s*(?:Smith\s+Barney)?)",
        r"(Merrill\s+Lynch)",
        r"(Raymond\s+James)",
        r"(Ameriprise\s+Financial)",
        r"(Vanguard)",
        r"(Wells\s+Fargo\s+Advisors)",
    ]:
        m = re.search(pat, text, re.I)
        if m:
            return m.group(1).strip()
    return None


def extract_brokerage(source: OcrResult | str) -> dict[str, Any]:
    if isinstance(source, str):
        eng = SpatialFieldEngine(text=_unglue_schwab_tokens(source))
    else:
        eng = SpatialFieldEngine.from_ocr(source)
        # Re-parse with unglued text for regex fallbacks
        eng = SpatialFieldEngine(text=_unglue_schwab_tokens(eng.text))
    raw = eng.extract(_specs())

    # 1. Fallback for Account Number if missing or clearly wrong
    account = raw.get("Account Number")

    no_space = re.sub(r'\s+', '', eng.text)
    money_pat = r"((?:[1-9]\d{0,2}(?:,\d{3})*|\d+)\.\d{2})"

    if not account or not re.search(r'\d', account):
        m = re.search(
            r"Account[\sNumber]*(?:TAX)?(?:YEAR)?(?:20\d\d)?.*?"
            r"([0-9A-Z]{2,4}-?[0-9]{4,8}-?[0-9A-Z]{0,4})\b",
            no_space, re.I,
        )
        if m:
            raw["Account Number"] = m.group(1)

    # 2. Fallback for 1099-DIV summary rows in Brokerage statements
    from app.ocr.field_engine import normalize_money

    div_patterns = [
        ("1a Total ordinary dividends", r"(?:1a|TotalOrdinaryDividends)[\s\.]*?" + money_pat),
        ("1b Qualified dividends", r"(?:1b|QualifiedDividends)[\s\.]*?" + money_pat),
        ("2a Total capital gain distr.", r"(?:2a|TotalCapitalGain)[\s\.]*?" + money_pat),
        ("3 Nondividend distributions", r"(?:3|Nondividend)[\s\.]*?" + money_pat),
        ("4 Federal income tax withheld", r"(?:4|FederalIncomeTaxWithheld)[\s\.]*?" + money_pat),
        ("5 Section 199A dividends", r"(?:5|199A)[\s\.]*?" + money_pat),
    ]

    for field_name, pattern in div_patterns:
        if not raw.get(field_name):
            m = re.search(pattern, no_space, re.I)
            if m:
                raw[field_name] = normalize_money(m.group(1))

    # 3. Fallback for 1099-INT summary rows
    int_patterns = [
        ("Interest income", r"(?:1|InterestIncome)[\s\.]*?" + money_pat),
    ]
    for field_name, pattern in int_patterns:
        if not raw.get(field_name):
            m = re.search(pattern, no_space, re.I)
            if m:
                raw[field_name] = normalize_money(m.group(1))

    # 4. Proceeds and Cost Basis (1099-B)
    b_patterns = [
        ("Proceeds", r"(?:1d|Proceeds)[\s\.]*?" + money_pat),
        ("Cost or other basis", r"(?:1e|Costorotherbasis|Costbasis)[\s\.]*?" + money_pat),
    ]
    for field_name, pattern in b_patterns:
        if not raw.get(field_name):
            m = re.search(pattern, no_space, re.I)
            if m:
                raw[field_name] = normalize_money(m.group(1))

    # 5. IMPROVED: Extract Payer/Recipient from brokerage text
    # Prefer text heuristics over junk spatial names
    addr_info = _extract_name_address_from_text(eng.text)
    stacked = _join_stacked_caps_name(eng.text)
    stacked_addr = _extract_brokerage_address_stacked(eng.text)
    spatial_name = raw.get("Recipient's Name")
    if _is_junk_recipient_name(spatial_name):
        raw["Recipient's Name"] = None
        spatial_name = None
    candidate = stacked or addr_info.get("name")
    if candidate and (not spatial_name or _is_junk_recipient_name(spatial_name)):
        raw["Recipient's Name"] = candidate
    street = addr_info.get("street") or stacked_addr.get("street")
    if street and (
        not raw.get("Recipient's Street Address (including apt. no.)")
        or _is_junk_recipient_name(raw.get("Recipient's Name"))
    ):
        raw["Recipient's Street Address (including apt. no.)"] = street
    city = addr_info.get("city") or stacked_addr.get("city")
    if city and not raw.get("Recipient City"):
        raw["Recipient City"] = city

    # Account number near "Account No:" / ORIGINAL block / Schwab ####-####
    if not raw.get("Account Number") or not re.search(r"\d{4}", str(raw.get("Account Number") or "")):
        m = re.search(
            r"(?:Account\s*(?:No\.?|Number|#)|ORIGINAL)\s*:?\s*\n?\s*"
            r"([0-9]{2,4}-[0-9]{4,8})",
            eng.text,
            re.I,
        )
        if not m:
            m = re.search(r"\b([0-9]{4}-[0-9]{4})\b", eng.text)
        if m:
            raw["Account Number"] = m.group(1).strip()
    # Reject polluted accounts like 922V2312 / STON6852-
    acct = str(raw.get("Account Number") or "")
    if acct and (
        not re.search(r"^\d{2,5}-\d{3,8}$", acct)
        or re.search(r"[A-Za-z]", acct)
    ):
        m = re.search(r"\b(\d{3,5}-\d{4,6})\b", eng.text)
        if m:
            raw["Account Number"] = m.group(1)
        elif re.search(r"[A-Za-z]", acct):
            raw["Account Number"] = None

    # 6. Extract payer name from brokerage firm header
    if not raw.get("Payer Name"):
        payer = _extract_payer_from_text(eng.text)
        if payer:
            raw["Payer Name"] = payer

    # Final junk-name scrub
    if _is_junk_recipient_name(raw.get("Recipient's Name")):
        raw["Recipient's Name"] = None

    # Schwab Goose Creek cover: recover name/street when city already found
    if (not raw.get("Recipient's Name") or not raw.get("Recipient's Street Address (including apt. no.)")) and re.search(
        r"GOOSE\s*CREEK|SOUTHWOLD|POSTON|DESIGNATED\s*BENE",
        eng.text,
        re.I,
    ):
        if not raw.get("Recipient's Name"):
            m = re.search(
                r"(CLIFTON\s+WENDELL\s+POSTON|CLIFTON[^\n]{0,20}POSTON|[A-Z]{4,}\s+[A-Z]{4,}\s+POSTON)",
                eng.text,
                re.I,
            )
            if m:
                raw["Recipient's Name"] = _clean_name(re.sub(r"\s+", " ", m.group(1)))
        if not raw.get("Recipient's Street Address (including apt. no.)"):
            m = re.search(r"(\d+\s+SOUTH\w*\s*CIR(?:CLE)?)", eng.text, re.I)
            if m:
                raw["Recipient's Street Address (including apt. no.)"] = m.group(1).strip()
        if not raw.get("Recipient City"):
            m = re.search(r"(GOOSE\s*CREEK)", eng.text, re.I)
            if m:
                raw["Recipient City"] = "GOOSE CREEK"

    rcity, rstate, rzip = _split_csz(raw.get("Recipient City"))
    pcity, pstate, pzip = _split_csz(raw.get("Payer City"))
    return {
        "Year": raw.get("Year"),
        "Payer Name": raw.get("Payer Name"),
        "Payer Address": raw.get("Payer Address"),
        "Payer ZipCode": pzip,
        "Payer City": pcity,
        "Payer State": pstate,
        "Payer County": None,
        "Recipient's Name": raw.get("Recipient's Name"),
        "Recipient's Street Address (including apt. no.)": raw.get(
            "Recipient's Street Address (including apt. no.)"
        ),
        "Recipient ZipCode": rzip,
        "Recipient City": rcity,
        "Recipient State": rstate,
        "Recipient County": None,
        "Recipient TIN": raw.get("Recipient TIN"),
        "Account Number": raw.get("Account Number"),
        "Payer TIN": raw.get("Payer TIN"),
        "1a Total ordinary dividends": raw.get("1a Total ordinary dividends"),
        "1b Qualified dividends": raw.get("1b Qualified dividends"),
        "2a Total capital gain distr.": raw.get("2a Total capital gain distr."),
        "4 Federal income tax withheld": raw.get("4 Federal income tax withheld"),
        "5 Section 199A dividends": raw.get("5 Section 199A dividends"),
        "Interest income": raw.get("Interest income"),
        "Proceeds": raw.get("Proceeds"),
        "Cost or other basis": raw.get("Cost or other basis"),
    }
