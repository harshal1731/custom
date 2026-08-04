"""Spatial / structural field engine for US tax OCR.

Uses OCR token positions when available. Falls back to synthetic line geometry
from plain text so unit tests and text-only paths still work.

Production rules are IRS structure only: labels, box numbers, value shapes.
No issuer or person names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.ocr.types import OcrPage, OcrResult, OcrToken


def _group_lines(tokens: list[OcrToken], y_tol: int = 18) -> list[str]:
    if not tokens:
        return []
    ordered = sorted(tokens, key=lambda t: (t.top, t.left))
    lines: list[list[OcrToken]] = []
    current: list[OcrToken] = []
    current_y: float | None = None
    for tok in ordered:
        if current_y is None or abs(tok.cy - current_y) <= y_tol:
            current.append(tok)
            current_y = tok.cy if current_y is None else (current_y * 0.7 + tok.cy * 0.3)
        else:
            lines.append(sorted(current, key=lambda t: t.left))
            current = [tok]
            current_y = tok.cy
    if current:
        lines.append(sorted(current, key=lambda t: t.left))
    return [" ".join(t.text for t in line) for line in lines]

_MONEY_RE = re.compile(
    r"^(?:\$\s*)?-?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}$"
)
_SSN_RE = re.compile(
    r"^(?:X{3}|x{3}|\*{3}|\d{3})-(?:X{2}|x{2}|\*{2}|\d{2})-\d{4}$"
)
_EIN_RE = re.compile(r"^(?:\d{2}-\d{7}|\d{9})$")
_YEAR_RE = re.compile(r"^20\d{2}$")
_ST_SUFFIX = (
    r"(?:STREET|AVENUE|DRIVE|LANE|COURT|CIRCLE|PLACE|PARKWAY|"
    r"ST|AVE|RD|ROAD|DR|WAY|LN|BLVD|CT|CIR|PL|HWY|PKWY|PK|"
    r"TRAIL|TRL|TER|TERRACE|LOOP|RUN|PATH|PIKE|SQ|SQUARE)\.?"
)
_STREET_RE = re.compile(
    rf"(?:P\.?\s*O\.?\s*BOX\s*[A-Za-z0-9\-]+|PO\s*BOX\s*[A-Za-z0-9\-]+|"
    rf"\d+[A-Za-z0-9 .#'\-/]{{0,50}}?(?:(?<=\s)|(?<=\d)){_ST_SUFFIX}\b)",
    re.I,
)
_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN",
    "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV",
    "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN",
    "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}
_OMB_ACCOUNTS = {"1545-0110", "1545-0112", "1545-1518", "1545-0008"}

_BOILERPLATE = re.compile(
    r"(?:street address|city or town|state or province|foreign postal|telephone|"
    r"OMB\s*No|Form\s*1099|Form\s*5498|Form\s*W-2|Fom\s*1099|Rev\.|"
    r"calendar year|Copy\s*[ABC]|important tax|furnished to|Payer'?s?\s*RTN|"
    r"Interest income|ordinary dividends|Fair market value|Rollover|Archer MSA|"
    r"Medicare|Participant\b|see instructions|CORRECTED|"
    r"Department of the Treasury|Internal Revenue|For Recipient|"
    r"Summary Totals|Return Service|This is important|negligence|sanction|"
    r"keep for your records|www\.irs\.gov|DIVIDENDS|Distributions|"
    r"DESIGNATED|Account of|TAXYEAR|COMPOSITE|YEAR-END|Holder Account|"
    r"Record Date|Control#|IMPORTANT TAX|Within USA|Hearing Impaired|"
    r"Please see reverse|NOTNEGOTIABLE|Itemsfor Attention|Date Prepared|"
    r"TaxpayerID|Federal IDNumber|TelephoneNumber|Box Description|"
    r"Table of Contents|Combined Statement|ACCOUNT NUMBER|BOX#|"
    r"PAYER'?S?\s*TIN|RECIPIENT'?S?\s*TIN|CUSTOMER SERV|been reported|"
    r"Instructions for Recipient|Forwarding Service|"
    r"is being furnished|If you are required|required to file|nished to the IRS|"
    r"tax information|file a return|negligence penalty|important tax)",
    flags=re.I,
)

_INSTRUCTION_NOISE = re.compile(
    r"(?:\b(?:IRS|required|furnished|negligence|information|return|file|"
    r"important|sanction|instructions|recipient|payer|account|tax year|"
    r"1099|being|nished|advocacy|team|department|attention)\b|\.{2,})",
    flags=re.I,
)

_CORPORATE_NAME = re.compile(
    r"\b(?:Team|Advocacy|Department|Services|Attention|Internal Revenue|"
    r"Customer Service|Support|Inquiries|Inc\.?|LLC|Corp)\b",
    re.I,
)
_STREET_LABEL_NOISE = re.compile(
    r"\b(?:INTERE|INTEREST|FEDERAL|ORDINARY|QUALIFIED|DESCRIPTION|NUMBER|"
    r"BOX|STATE|TOTAL|DASHBOA)\b",
    re.I,
)

# Role → label phrases used to anchor address blocks (IRS vocabulary only).
ROLE_LABELS: dict[str, list[str]] = {
    "payer": [
        "payer's name, street address",
        "payer's name, address",
        "payer's name and address",
        "payer's name",
        "payer's details",
        "payers name",
    ],
    "recipient": [
        "recipient's name, street address",
        "recipient's name and address",
        "recipient's name",
        "recipients name",
        "recipient's-name",
        "customer's name",
        "customer:",
    ],
    "employer": [
        "employer's name, address, and zip code",
        "employers name, address, and zip code",
        "employer's name, address, and zlp code",
        "employers name, address, and zlp code",
        "employer's name, address, and zip",
    ],
    "employee": [
        "employee's name, address, and zip code",
        "employees name, address, and zip code",
        "employee's name, address, and zlp code",
        "employees name, address, and zlp code",
        "employee's name, address, and zip",
    ],
    "trustee": [
        "trustee's name, street address",
        "trustee's or issuer's name",
        "trustee's name",
    ],
    "participant": [
        "participant's name",
        "participants name",
    ],
}


@dataclass
class FieldSpec:
    key: str
    value_type: str
    labels: list[str] = field(default_factory=list)
    box: str | None = None
    role: str | None = None
    sum_repeats: bool = False
    default: Any = None
    part: str | None = None  # for address_block: name|street|city|combined


@dataclass
class Line:
    text: str
    tokens: list[OcrToken]
    top: float
    left: float
    right: float
    bottom: float

    @property
    def cy(self) -> float:
        return (self.top + self.bottom) / 2


def normalize_money(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().replace("$", "").replace(",", "").replace(" ", "")
    cleaned = cleaned.replace("O", "0").replace("o", "0")
    if re.fullmatch(r"-?\d+(\.\d{1,2})?", cleaned):
        return cleaned
    return None


def format_ein(raw: str) -> str:
    d = re.sub(r"\D", "", raw)
    return f"{d[:2]}-{d[2:]}" if len(d) == 9 else raw


def format_ssn(raw: str) -> str:
    return raw.upper().replace("*", "X")


def clean(s: str | None) -> str | None:
    if not s:
        return None
    s = re.sub(r"\s+", " ", s).strip(" ,;|")
    return s or None


def normalize_label(s: str) -> str:
    s = s.lower()
    s = s.replace("'", "").replace("'", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # common OCR letter confusions in labels
    s = s.replace("zlp", "zip").replace("zipcode", "zip code")
    s = s.replace("eariy", "early").replace("fom ", "form ")
    return s


def tokens_from_text(text: str, line_height: int = 24) -> list[OcrToken]:
    """Synthesize left-to-right tokens from plain OCR text (tests / fallback)."""
    tokens: list[OcrToken] = []
    for i, ln in enumerate(text.splitlines()):
        x = 0
        for word in ln.split():
            w = max(8, len(word) * 10)
            tokens.append(
                OcrToken(
                    text=word,
                    confidence=1.0,
                    left=x,
                    top=i * line_height,
                    right=x + w,
                    bottom=i * line_height + line_height - 4,
                )
            )
            x += w + 8
    return tokens


def page_from_text(text: str) -> OcrPage:
    tokens = tokens_from_text(text)
    lines = _group_lines(tokens) if tokens else [ln for ln in text.splitlines() if ln.strip()]
    return OcrPage(
        page_number=1,
        text=text,
        lines=lines,
        tokens=tokens,
        width=max((t.right for t in tokens), default=800),
        height=max((t.bottom for t in tokens), default=1000),
    )


def result_from_text(text: str) -> OcrResult:
    return OcrResult(pages=[page_from_text(text)])


class SpatialFieldEngine:
    def __init__(self, page: OcrPage | None = None, text: str | None = None):
        if page is None:
            if text is None:
                raise ValueError("page or text required")
            page = page_from_text(text)
        elif text is not None and (not page.tokens or all(t.left == 0 and t.top == 0 for t in page.tokens)):
            # Tokens without geometry — rebuild from text
            page = page_from_text(text if text else page.text)

        self.page = page
        self.text = page.text or (text or "")
        self.lines = self._build_lines(page.tokens)
        if not self.lines and self.text:
            self.page = page_from_text(self.text)
            self.lines = self._build_lines(self.page.tokens)

    @staticmethod
    def from_ocr(ocr: OcrResult, prefer_left_half: bool = False) -> SpatialFieldEngine:
        if not ocr.pages:
            return SpatialFieldEngine(text="")
        page = ocr.pages[0]
        if prefer_left_half and page.width > 0:
            mid = page.width / 2
            toks = [t for t in page.tokens if t.cx <= mid]
            if toks:
                page = OcrPage(
                    page_number=page.page_number,
                    text="\n".join(_group_lines(toks)),
                    lines=_group_lines(toks),
                    tokens=toks,
                    width=page.width,
                    height=page.height,
                )
        # Drop bottom Copy C reprints when present in text
        text = page.text
        parts = re.split(r"(?m)^Copy\.?\s*C\s*[.\-]", text, maxsplit=1, flags=re.I)
        if len(parts) > 1 and len(parts[0]) > 80:
            # Keep tokens in upper portion
            cut_y = page.height * 0.55 if page.height else None
            if cut_y:
                toks = [t for t in page.tokens if t.top <= cut_y]
                if toks:
                    page = OcrPage(
                        page_number=page.page_number,
                        text="\n".join(_group_lines(toks)),
                        lines=_group_lines(toks),
                        tokens=toks,
                        width=page.width,
                        height=page.height,
                    )
            else:
                page = page_from_text(parts[0])
        return SpatialFieldEngine(page=page)

    def _build_lines(self, tokens: list[OcrToken], y_tol: int = 18) -> list[Line]:
        if not tokens:
            return []
        ordered = sorted(tokens, key=lambda t: (t.top, t.left))
        groups: list[list[OcrToken]] = []
        current: list[OcrToken] = []
        current_y: float | None = None
        for tok in ordered:
            if current_y is None or abs(tok.cy - current_y) <= y_tol:
                current.append(tok)
                current_y = tok.cy if current_y is None else (current_y * 0.7 + tok.cy * 0.3)
            else:
                groups.append(sorted(current, key=lambda t: t.left))
                current = [tok]
                current_y = tok.cy
        if current:
            groups.append(sorted(current, key=lambda t: t.left))
        lines: list[Line] = []
        for g in groups:
            text = " ".join(t.text for t in g)
            lines.append(
                Line(
                    text=text,
                    tokens=g,
                    top=min(t.top for t in g),
                    left=min(t.left for t in g),
                    right=max(t.right for t in g),
                    bottom=max(t.bottom for t in g),
                )
            )
        return lines

    def extract(self, specs: Iterable[FieldSpec]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        # Precompute parties by role once
        parties: dict[str, dict[str, str | None]] = {}
        for spec in specs:
            if spec.value_type == "address_block" and spec.role and spec.role not in parties:
                parties[spec.role] = self.find_party(spec.role)

        for spec in specs:
            val = self._resolve(spec, parties)
            if val is None and spec.default is not None:
                val = spec.default
            out[spec.key] = val
        return out

    def _resolve(self, spec: FieldSpec, parties: dict[str, dict[str, str | None]]) -> Any:
        vt = spec.value_type
        if vt == "address_block":
            party = parties.get(spec.role or "", {})
            if not party and spec.role:
                party = self.find_party(spec.role)
            part = spec.part or "combined"
            if part == "combined":
                bits = [party.get("name"), party.get("street"), party.get("city")]
                return clean(", ".join(p for p in bits if p))
            return party.get(part)

        if vt == "year":
            return self.find_year(spec.labels)

        if vt == "tin_ssn":
            return self.find_ssn(spec.labels)

        if vt == "tin_ein":
            return self.find_ein(spec.labels)

        if vt == "account":
            return self.find_account(spec.labels)

        if vt == "money":
            if spec.sum_repeats and spec.box:
                summed = self.sum_box_amounts(spec.labels, spec.box)
                if summed is not None:
                    return summed
            return self.find_money(spec.labels, spec.box)

        if vt == "checkbox":
            return self.find_checkbox(spec.labels)

        if vt == "raw":
            return self.find_raw_after_label(spec.labels)

        if vt == "name_split":
            # W-2 style first/last from employee name line
            party = parties.get(spec.role or "employee") or self.find_party(spec.role or "employee")
            name = party.get("name") or ""
            parts = [p for p in name.split() if re.search(r"[A-Za-z]", p)]
            if len(parts) >= 4 and len(parts) % 2 == 0:
                half = len(parts) // 2
                if [p.lower() for p in parts[:half]] == [p.lower() for p in parts[half:]]:
                    parts = parts[:half]
            if spec.part == "first":
                return parts[0] if parts else None
            if spec.part == "last":
                return parts[-1] if len(parts) >= 2 else None
            return clean(name) if name else None

        return None

    # ----- finders -----

    def find_label_line(self, labels: list[str]) -> tuple[int, Line] | None:
        norms = [normalize_label(l) for l in labels if l]
        for i, line in enumerate(self.lines):
            ln = normalize_label(line.text)
            for n in norms:
                if n and n in ln:
                    return i, line
        return None

    def find_year(self, labels: list[str] | None = None) -> str | None:
        if labels:
            hit = self.find_label_line(labels)
            if hit:
                i, _ = hit
                window = " ".join(self.lines[j].text for j in range(i, min(i + 3, len(self.lines))))
                m = re.search(r"\b(20\d{2})\b", window)
                if m:
                    return m.group(1)
        for pat in (
            r"(?:Tax\s*Year|TAXYEAR|For\s*calendar\s*year|calendar\s*year)\s*[:#]?\s*(20\d{2})",
            r"\b(20\d{2})\b",
        ):
            m = re.search(pat, self.text, flags=re.I)
            if m:
                return m.group(1)
        return None

    def find_ssn(self, labels: list[str] | None = None) -> str | None:
        if labels:
            hit = self.find_label_line(labels)
            if hit:
                i, line = hit
                for j in range(i, min(i + 4, len(self.lines))):
                    ssn = self._ssn_in(self.lines[j].text)
                    if ssn:
                        return ssn
                    # next-line only digits/mask
                    if j > i:
                        ssn = self._ssn_in(self.lines[j].text.split()[0] if self.lines[j].text else "")
                        if ssn:
                            return ssn
        return self._ssn_in(self.text)

    def _ssn_in(self, s: str) -> str | None:
        m = re.search(
            r"\b((?:X{3}|x{3}|\*{3}|\d{3})-(?:X{2}|x{2}|\*{2}|\d{2})-\d{4})\b",
            s,
        )
        if m:
            return format_ssn(m.group(1))
        m = re.search(r"(?:\*+|X+|x+)[*\-Xx]*(\d{4})\b", s)
        if m:
            return f"XXX-XX-{m.group(1)}"
        return None

    def find_ein(self, labels: list[str] | None = None) -> str | None:
        if labels:
            hit = self.find_label_line(labels)
            if hit:
                i, _ = hit
                for j in range(i, min(i + 4, len(self.lines))):
                    ein = self._ein_in(self.lines[j].text)
                    if ein:
                        return ein
        # labeled anywhere
        m = re.search(
            r"(?:Payer'?s?\s*(?:Federal\s*)?(?:ID(?:\s*No\.?)?|TIN)|PAYER'?S?\s*TIN|"
            r"TRUSTEE'?S?.{0,60}identification number|Payer'?s?\s*ID\s*Number|"
            r"Federal\s*ID\s*Number|Employer identification number(?:\s*\(EIN\))?|"
            r"E\.?I\.?N\.?)\s*[:#]?\s*(\d{2}-?\d{7}|\d{9})",
            self.text,
            flags=re.I | re.S,
        )
        if m:
            return format_ein(m.group(1))
        m = re.search(r"\b(\d{2}-\d{7})\b", self.text)
        return m.group(1) if m else None

    def _ein_in(self, s: str) -> str | None:
        m = re.search(r"\b(\d{2}-\d{7})\b", s)
        if m:
            return m.group(1)
        m = re.search(r"\b(\d{9})\b", s)
        if m:
            return format_ein(m.group(1))
        return None

    def _valid_account(self, val: str | None) -> str | None:
        val = clean(val)
        if not val or val in _OMB_ACCOUNTS:
            return None
        if re.search(r"[A-Z]{2}\d{5}", val.replace(" ", ""), re.I):
            return None
        if re.search(
            r"^(?:State|CUSIP|Form|bond|TAX|Number|TAXYEAR|HOLDER|OMB|see|inst)",
            val,
            re.I,
        ):
            return None
        if re.fullmatch(r"[A-Za-z]{1,8}", val):
            return None
        if not re.fullmatch(r"[A-Za-z0-9X\-]{4,30}", val):
            return None
        return val

    def find_account(self, labels: list[str] | None = None) -> str | None:
        # Table: account before "Interest income 1" — prefer max interest account
        best = None
        best_amt = -1.0
        for m in re.finditer(
            r"(?m)^(\d{6,12})\s+Interest income\s+1\s+([0-9,]+\.\d{2})",
            self.text,
            flags=re.I,
        ):
            amt = float(m.group(2).replace(",", ""))
            if amt > best_amt:
                best_amt = amt
                best = m.group(1)
        if best:
            return best

        for pat in (
            r"Account Number\s*([0-9]{4}-[0-9]{4})",
            r"Account\s*Number\s*[:#]?\s*([0-9]{6,12})\b",
            r"Account\s*Number\s*[:#]\s*([A-Za-z0-9][A-Za-z0-9\-/]{3,30})",
            r"\b(C\d{7,})\b",
            r"Account\s*Number\s*[:#]?\s*([0-9]{10,})",
            r"Holder\s*Account\s*Number\s*(?:\r?\n|\s)*(?:[A-Z0-9\- ]{0,40})?(C\d{7,})",
        ):
            m = re.search(pat, self.text, flags=re.I)
            if not m:
                continue
            val = self._valid_account(m.group(1))
            if val:
                return val

        # Masked / alphanumeric under Account number label (skip CUSIP/bond lines)
        hit = self.find_label_line(labels or ["Account number", "Account Number"])
        if hit:
            i, line = hit
            same = re.search(
                r"Account\s*Number\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-]{3,30})",
                line.text,
                flags=re.I,
            )
            if same:
                val = self._valid_account(same.group(1))
                if val:
                    return val
            for j in range(i + 1, min(i + 6, len(self.lines))):
                for tok in self.lines[j].text.split():
                    val = self._valid_account(tok)
                    if val and (re.search(r"\d", val) or val.startswith("X") or val.startswith("C")):
                        return val
        return None

    def find_money(self, labels: list[str] | None, box: str | None) -> str | None:
        candidates: list[str] = []

        if labels:
            hit = self.find_label_line(labels)
            if hit:
                i, line = hit
                for j in range(i, min(i + 5, len(self.lines))):
                    for tok in self.lines[j].tokens:
                        if j == i and tok.left + 2 < line.left:
                            continue
                        val = normalize_money(tok.text)
                        if val and re.search(r"\d+\.\d{2}", tok.text):
                            candidates.append(val)
                            break
                    if candidates:
                        break
                    m = re.search(
                        r"(?:\$\s*)?((?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})",
                        self.lines[j].text,
                    )
                    if m:
                        candidates.append(normalize_money(m.group(1)) or "")
                        break

        if box:
            m = re.search(
                rf"(?<![\dA-Za-z]){re.escape(box)}(?![\dA-Za-z])\s*[).:\-]?\s*"
                rf"(?:[A-Za-z][^\n$]{{0,60}}?)?\$?\s*"
                rf"((?:\d{{1,3}}(?:,\d{{3}})+|\d+)\.\d{{2}})",
                self.text,
                flags=re.I | re.M,
            )
            if m:
                candidates.append(normalize_money(m.group(1)) or "")

        # Copy B pattern $amount year (often the true per-form amount)
        m = re.search(r"\$\s*([0-9,]+\.\d{2})\s+20\d{2}", self.text)
        copy_b = normalize_money(m.group(1)) if m else None
        if copy_b:
            candidates.append(copy_b)

        candidates = [c for c in candidates if c]
        if not candidates:
            return None
        # Prefer Copy B when a larger summary total was also captured
        if copy_b and any(float(c) > float(copy_b) for c in candidates):
            return copy_b
        return candidates[0]

    def sum_box_amounts(self, labels: list[str] | None, box: str) -> str | None:
        label = (labels or [""])[0]
        if not label:
            return None
        # Allow partial label match in table rows
        pats = [
            re.compile(
                rf"{re.escape(label)}\s+{re.escape(box)}\s+\$?\s*([0-9,]+\.\d{{2}})",
                re.I,
            ),
            re.compile(
                rf"{re.escape(label)}[^\n]{{0,40}}?\s+{re.escape(box)}\s+\$?\s*([0-9,]+\.\d{{2}})",
                re.I,
            ),
        ]
        vals: list[float] = []
        for pat in pats:
            for m in pat.finditer(self.text):
                v = normalize_money(m.group(1))
                if v is not None:
                    vals.append(float(v))
            if vals:
                break
        if not vals:
            return None
        return f"{sum(vals):.2f}"

    def _first_money(self, s: str) -> str | None:
        m = re.search(r"(?:\$\s*)?((?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})", s)
        return normalize_money(m.group(1)) if m else None

    def find_checkbox(self, labels: list[str]) -> str | None:
        hit = self.find_label_line(labels)
        if not hit:
            if re.search(r"FATCA", self.text, re.I):
                if re.search(r"FATCA.{0,40}(?:\[X\]|☑|■)", self.text, re.I | re.S):
                    return "Yes"
                if re.search(r"FATCA.{0,40}□", self.text, re.I | re.S):
                    return "No"
            return None
        i, _ = hit
        window = " ".join(self.lines[j].text for j in range(i, min(i + 3, len(self.lines))))
        if re.search(r"(?:\[X\]|☑|■)", window):
            return "Yes"
        if "□" in window:
            return "No"
        # HSA type mark
        if re.search(r"\bHSA\b", window, re.I):
            return "Yes"
        return None

    def find_raw_after_label(self, labels: list[str]) -> str | None:
        hit = self.find_label_line(labels)
        if not hit:
            return None
        i, line = hit
        # colon value on same line
        for lab in labels:
            m = re.search(rf"{re.escape(lab)}\s*:\s*(.+)$", line.text, flags=re.I)
            if m:
                return clean(m.group(1).split(",")[0])
        if i + 1 < len(self.lines):
            return clean(self.lines[i + 1].text)
        return None

    # ----- parties / address -----

    def find_party(self, role: str) -> dict[str, str | None]:
        labels = ROLE_LABELS.get(role, [])

        # 1) Colon-labeled fields (broker letters): "Payer's name: X"
        colon = self._colon_party(labels)
        if colon.get("name") and (colon.get("street") or colon.get("city") or role == "payer"):
            # Enrich payer address from "Payer's address:" if needed
            if role == "payer" and not colon.get("street"):
                colon = self._enrich_payer_address(colon)
            if colon.get("name"):
                return colon

        # 2) Block after IRS header labels
        party = self._party_after_labels(labels)
        if self._party_quality(party, role):
            return party

        # 3) Role-specific fallbacks
        if role in {"recipient", "participant", "employee"}:
            party = self._recipient_street_anchor_party()
            if self._party_quality(party, role):
                return party
            party = self._mail_panel_party()
            if self._party_quality(party, role):
                return party
            # "Recipient NAME" on one line (compact DIV layouts)
            m = re.search(
                r"(?m)^Recipient\s+([A-Z][A-Z0-9 ]{3,50})\s*$",
                self.text,
                flags=re.I,
            )
            if m:
                name = self._scrub_name(m.group(1))
                idx = next(
                    (i for i, ln in enumerate(self.lines) if "Recipient" in ln.text and m.group(1)[:6] in ln.text),
                    None,
                )
                chunk = []
                if idx is not None:
                    chunk = [self.lines[j].text for j in range(idx + 1, min(idx + 4, len(self.lines)))]
                rest = self._parse_address_triplet([name or ""] + chunk)
                rest["name"] = name
                if self._party_quality(rest, role):
                    return rest

        if role in {"payer", "trustee", "employer"}:
            party = self._letterhead_org_party()
            if self._party_quality(party, role):
                return party

        return {"name": None, "street": None, "city": None}

    def _party_quality(self, party: dict[str, str | None], role: str) -> bool:
        name = party.get("name") or ""
        if not name or _BOILERPLATE.search(name):
            return False
        if re.match(r"^\d+\s", name):
            return False
        if role in {"payer", "trustee", "employer"}:
            return bool(party.get("street") or party.get("city") or self._looks_org(name))
        if not self._looks_person_name(name):
            return False
        return bool(party.get("street") or party.get("city"))

    def _colon_party(self, labels: list[str]) -> dict[str, str | None]:
        for lab in labels:
            # Allow optional trailing punctuation in label
            lab_pat = re.escape(lab.rstrip(":"))
            m = re.search(rf"{lab_pat}\s*:\s*([^\n]+)", self.text, flags=re.I)
            if not m:
                continue
            name = clean(m.group(1).split(",")[0])
            if not name or _BOILERPLATE.search(name) or not self._looks_person_or_org_name(name):
                continue
            street = city = None
            # Narrative: Name Street City on nearby text
            addr = re.search(
                rf"{re.escape(name)}\s+({_STREET_RE.pattern})\s+"
                rf"([A-Za-z .]+,?\s*[A-Z]{{2}}\s*\d{{5}}(?:-\d{{4}})?(?:\s+USA)?)",
                self.text,
                flags=re.I,
            )
            if addr:
                street = self._norm_street(addr.group(1))
                city = self._norm_city(addr.group(2))
            return {"name": self._scrub_name(name), "street": street, "city": city}
        return {"name": None, "street": None, "city": None}

    def _enrich_payer_address(self, party: dict[str, str | None]) -> dict[str, str | None]:
        m = re.search(r"Payer'?s?\s*address\s*:\s*([^\n]+)", self.text, flags=re.I)
        if not m:
            return party
        raw = clean(m.group(1)) or ""
        sm = re.search(rf"({_STREET_RE.pattern})\s*,?\s*(.+)$", raw, flags=re.I)
        if sm:
            party["street"] = self._norm_street(sm.group(1))
            party["city"] = self._norm_city(sm.group(2))
        elif raw:
            party["street"] = raw
        return party

    def _party_after_labels(self, labels: list[str]) -> dict[str, str | None]:
        hit = self.find_label_line(labels)
        if not hit:
            return {"name": None, "street": None, "city": None}
        i, line = hit
        # Same-line colon value
        for lab in labels:
            m = re.search(rf"{re.escape(lab.rstrip(':'))}\s*:\s*(.+)$", line.text, flags=re.I)
            if m:
                name = self._scrub_name(m.group(1).split(",")[0])
                chunk = [self.lines[j].text for j in range(i + 1, min(i + 6, len(self.lines)))]
                rest = self._parse_address_triplet([name or ""] + chunk)
                if name:
                    rest["name"] = name
                return rest
        chunk = [self.lines[j].text for j in range(i + 1, min(i + 10, len(self.lines)))]
        return self._parse_address_triplet(chunk)

    def _recipient_street_anchor_party(self) -> dict[str, str | None]:
        """Find person address by house-number street line (bank letter / mail panel layouts)."""
        best: dict[str, str | None] | None = None
        best_score = -1
        for i, line in enumerate(self.lines):
            raw = self._normalize_mashed_street_line(line.text)
            sm = _STREET_RE.search(raw)
            if not sm:
                continue
            street_raw = sm.group(0)
            if re.search(r"P\.?\s*O\.?\s*BOX|PO\s*BOX", street_raw, re.I):
                continue
            if not re.match(r"\d", street_raw.strip()):
                continue
            if _STREET_LABEL_NOISE.search(street_raw):
                continue
            street = self._norm_street(street_raw)
            city = None
            for j in range(i, min(i + 3, len(self.lines))):
                cm = self._city_match(self.lines[j].text)
                if cm:
                    city = self._norm_city(cm)
                    break
            name = None
            for j in range(i - 1, max(i - 3, -1), -1):
                if j < 0:
                    break
                name = self._extract_person_name_from_line(self.lines[j].text)
                if name:
                    break
            if not name or not street:
                continue
            if _CORPORATE_NAME.search(name):
                continue
            if re.search(r"\b(?:SCHWAB|INC|LLC|CORP|BANK|TRUST|COMPANY|CO\.)\b", name, re.I):
                continue
            context = " ".join(
                self.lines[j].text for j in range(max(0, i - 1), min(len(self.lines), i + 3))
            )
            score = 1 + (2 if city else 0) + (2 if i > 4 else 0)
            if re.search(r"\b(?:CIR|DR|LN|CT|WAY|ST)\b", street, re.I):
                score += 1
            if re.search(r"\bCIR\b", street, re.I):
                score += 3
            if re.search(r"\d{4}-\d{4}", context):
                score += 4
            if re.search(
                r"Client Advocacy|Form1099|Internal Revenue Service|www\.|"
                r"Attention:|products and services",
                context,
                re.I,
            ):
                score -= 6
            if re.search(r"\b(?:WAY|BLVD|HWY|PIKE)\b", street, re.I) and re.search(
                r"\b(?:SCHWAB|INC|CORP|CO\.)\b", self.lines[max(0, i - 1)].text, re.I
            ):
                score -= 3
            if score > best_score:
                best_score = score
                best = {"name": name, "street": street, "city": city}
        return best or {"name": None, "street": None, "city": None}

    def _name_word_ok(self, word: str) -> bool:
        if re.fullmatch(r"(?:JR|SR)\.?", word, re.I):
            return True
        return len(word) >= 3 or bool(re.fullmatch(r"[A-Z]\.?", word))

    def _expand_mashed_name(self, name: str) -> str:
        compact = re.sub(r"[^A-Za-z]", "", name).upper()
        if len(compact) < 6 or " " in name.strip():
            return name
        for line in self.lines:
            lt = re.sub(
                r"^(?:Recipient|PAYER|EMPLOYEE|Employee)\s+",
                "",
                line.text.strip(),
                flags=re.I,
            )
            if re.sub(r"[^A-Za-z]", "", lt).upper() == compact and " " in lt:
                return lt
            for cand in re.findall(
                r"[A-Z][A-Za-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][A-Za-z]+){1,4}",
                lt,
            ):
                if re.sub(r"[^A-Za-z]", "", cand).upper() == compact:
                    return cand
        for line in self.lines:
            for tok in re.findall(r"[A-Za-z]{8,}", line.text):
                if re.sub(r"[^A-Za-z]", "", tok).upper() != compact:
                    continue
                for line2 in self.lines:
                    for cand in re.findall(
                        r"[A-Z][A-Za-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][A-Za-z]+){1,4}",
                        line2.text,
                    ):
                        if re.sub(r"[^A-Za-z]", "", cand).upper() == compact:
                            return cand
        return name

    def _extract_person_name_from_line(self, line: str) -> str | None:
        head = re.split(r"\s*&\s*", line, maxsplit=1)[0]
        head = re.split(
            r"\s+(?:[A-Z][A-Za-z]+\s+)?(?:CO\.|INC\.?|LLC|CORP|COMPANY|BANK|TRUST)\b",
            head,
            maxsplit=1,
            flags=re.I,
        )[0]
        line = clean(head) or line
        m = re.search(
            r"[-–]\s*([A-Z][A-Za-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][A-Za-z]+){1,3})",
            line,
        )
        if m:
            cand = self._scrub_name(m.group(1))
            if cand and self._looks_person_name(cand):
                return cand
        m = re.match(
            r"^[\-\s]*([A-Z][A-Za-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][A-Za-z]+)+)\s*$",
            line.strip(),
        )
        if m:
            cand = self._scrub_name(m.group(1))
            if cand and self._looks_person_name(cand):
                return cand
        for m in re.finditer(
            r"\b([A-Z][A-Za-z]{2,}(?:\s+[A-Z]\.?)?(?:\s+[A-Z][A-Za-z]{2,})+)\b",
            line,
        ):
            cand = self._scrub_name(m.group(1))
            if cand and self._looks_person_name(cand):
                return cand
        whole = self._scrub_name(line.strip())
        if whole and self._looks_person_name(whole):
            return whole
        words = line.split()
        for n in range(min(5, len(words)), 1, -1):
            cand = self._scrub_name(" ".join(words[:n]))
            if cand and self._looks_person_name(cand):
                return cand
        return None

    def _normalize_mashed_street_line(self, line: str) -> str:
        return re.sub(
            rf"(\d+)([A-Za-z]{{2,40}}?)({_ST_SUFFIX})\b",
            r"\1 \2 \3",
            line,
            flags=re.I,
        )

    def _mail_panel_party(self) -> dict[str, str | None]:
        stop = re.compile(
            r"PAYER'?S?\s*TIN|RECIPIENT'?S?\s*TIN|ACCOUNT NUMBER|FATCA|"
            r"Instructions for Recipient|TRUSTEE'?S?\s*federal",
            re.I,
        )
        for i, line in enumerate(self.lines):
            if stop.search(line.text):
                window = [self.lines[j].text for j in range(max(0, i - 6), i)]
                # City/street often glued onto the TIN label line
                if self._city_match(line.text) or _STREET_RE.search(line.text):
                    window = window + [line.text]
                party = self._parse_address_triplet(window)
                if party.get("name"):
                    return party
        # Explicit triplet anywhere early in document
        head = [ln.text for ln in self.lines[:35]]
        # Prefer person-like triplet (not org letterhead): scan from bottom of head upward
        for start in range(len(head) - 3, -1, -1):
            party = self._parse_address_triplet(head[start : start + 5])
            if party.get("name") and party.get("street") and not self._looks_org(party["name"] or ""):
                return party
        return {"name": None, "street": None, "city": None}

    def _letterhead_org_party(self) -> dict[str, str | None]:
        """Top-of-form organization + street + city (shape-based, no issuer list)."""
        for i, line in enumerate(self.lines[:25]):
            name_line = re.sub(r"\s+1099-[A-Z]{3}.*$", "", line.text, flags=re.I)
            name_line = re.sub(r"\s+for Tax Year.*$", "", name_line, flags=re.I)
            name_line = clean(name_line)
            if not name_line or not self._looks_org(name_line):
                # also allow ALLCAPS org without legal suffix if followed by PO BOX
                if not (
                    name_line
                    and re.search(r"^[A-Z0-9 &.,'-]{4,60}$", name_line)
                    and not _BOILERPLATE.search(name_line)
                    and i + 1 < len(self.lines)
                    and _STREET_RE.search(self.lines[i + 1].text)
                ):
                    continue
            name = name_line
            street = city = None
            for j in range(i + 1, min(i + 6, len(self.lines))):
                nxt = self.lines[j].text
                if re.search(r"^(?:COMPANY|N\.?A\.?|INC\.?|LLC)\b", nxt, re.I) and not street:
                    name = clean(f"{name} {nxt}")
                    continue
                raw = re.split(
                    r"\s+Interest income\b|\s+OMB\b|\s+Copy\b|\s+PAYER",
                    nxt,
                    flags=re.I,
                )[0]
                if not street and _STREET_RE.search(raw):
                    street = self._norm_street(raw)
                    cm = self._city_match(nxt)
                    if cm:
                        city = self._norm_city(cm)
                    continue
                if not city and self._city_match(raw):
                    city = self._norm_city(raw)
                    break
                if street and city:
                    break
            if name and (street or city):
                return {"name": name, "street": street, "city": city}
        return {"name": None, "street": None, "city": None}

    def _looks_org(self, s: str) -> bool:
        if not s or _BOILERPLATE.search(s):
            return False
        if re.match(r"^\d", s):
            return False
        return bool(
            re.search(
                r"\b(?:BANK|TRUST|CREDIT UNION|SAVINGS|N\.?A\.?|INC|LLC|CORP|"
                r"COMPANY|NATIONAL|FEDERAL|ASSOCIATION|CUSTODIAN)\b",
                s,
                re.I,
            )
        )

    def _parse_address_triplet(self, lines: list[str]) -> dict[str, str | None]:
        useful: list[str] = []
        for ln in lines:
            ln = clean(self._strip_box_noise(ln or ""))
            if not ln:
                continue
            # Strip trailing OCR noise glued onto name lines
            ln = re.sub(r"\s+been reported\.?$", "", ln, flags=re.I)
            ln = re.sub(r"\s+PAYER'?S?\s*TIN.*$", "", ln, flags=re.I)
            ln = clean(ln)
            if not ln:
                continue
            if _BOILERPLATE.search(ln) and not _STREET_RE.search(ln) and not self._city_match(ln):
                continue
            if normalize_money(ln) and re.fullmatch(r"\$?[\d,]+\.\d{2}", ln):
                continue
            if re.fullmatch(r"IRS|BOX|AMOUNT|DESCRIPTION", ln, re.I):
                continue
            useful.append(ln)

        name = street = city = None
        for ln in useful:
            if not name and self._looks_person_name(ln):
                name = self._scrub_name(ln)
                continue
            if not name and self._looks_person_or_org_name(ln) and not _INSTRUCTION_NOISE.search(ln):
                name = self._scrub_name(ln)
                continue
            if name and not street and _STREET_RE.search(ln):
                street = self._norm_street(_STREET_RE.search(ln).group(0))
                continue
            if name and not city and self._city_match(ln):
                city = self._norm_city(self._city_match(ln) or ln)
                break
        return {"name": name, "street": street, "city": city}

    def _looks_person_name(self, line: str) -> bool:
        if not line or _BOILERPLATE.search(line) or _INSTRUCTION_NOISE.search(line):
            return False
        core = re.split(
            r"\s+(?:FOR\s+TAX\s+YEAR|\d{3,5}\s+|1099-|and is being|furnished|required|information)\b",
            line,
            maxsplit=1,
            flags=re.I,
        )[0]
        core = re.sub(r"^[\-\s]+", "", core)
        if self._looks_org(core):
            return False
        if _CORPORATE_NAME.search(core):
            return False
        words = [w for w in core.split() if re.match(r"^[A-Za-z.'\-]+$", w)]
        max_words = 6 if any(re.fullmatch(r"(?:JR|SR)\.?", w, re.I) for w in words) else 5
        if not 2 <= len(words) <= max_words:
            return False
        if any(not self._name_word_ok(w) for w in words):
            return False
        letters = sum(c.isalpha() for c in core)
        return letters >= 4 and not _STREET_RE.search(core) and not self._city_match(core)

    def _looks_person_or_org_name(self, line: str) -> bool:
        if not line or _BOILERPLATE.search(line) or _INSTRUCTION_NOISE.search(line):
            return False
        if len(line) < 3 or len(line) > 90:
            return False
        if _STREET_RE.search(line) or self._city_match(line):
            return False
        if _SSN_RE.match(line) or _EIN_RE.match(line.replace("-", "") if line.isdigit() else line):
            return False
        if re.fullmatch(r"(?:X{3}|x{3}|\d{3})-(?:X{2}|x{2}|\d{2})-\d{4}", line):
            return False
        if re.fullmatch(r"\d{6,}", line) or re.fullmatch(r"\$?[\d,]+\.\d{2}", line):
            return False
        if re.search(r"Fom?\s*1099|Form\s*1099|Combined Statement", line, re.I):
            return False
        letters = sum(c.isalpha() for c in line)
        return letters >= 3

    def _scrub_name(self, name: str) -> str | None:
        name = re.split(
            r"\b(?:been reported|This is important|PAYER|RECIPIENT|FATCA|ACCOUNT|"
            r"Interest income|1 Interest|FOR TAX YEAR|1099-(?:INT|DIV|OID))\b",
            name,
            maxsplit=1,
            flags=re.I,
        )[0]
        name = re.sub(r"\s+\d{3,5}\s*$", "", name)
        name = re.sub(r"^[\-\s]+", "", name)
        if _INSTRUCTION_NOISE.search(name) and not self._looks_person_name(name):
            return None
        name = self._expand_mashed_name(name)
        name = re.sub(r"\b([A-Za-z]{3,})(JR|SR)\s*$", r"\1 \2", name, flags=re.I)
        return clean(name)

    def _strip_box_noise(self, line: str) -> str:
        line = re.split(
            r"\s+\d{1,2}[a-f]?\.?\s+(?:Interest|Federal|Total|Qualified|Foreign|"
            r"Tax-exempt|Market|Bond|Early|Investment|Nondividend|Section|Cash|"
            r"State|Rollover|Fair|Wages|Social|Medicare|Income|Employee|HSA)\b",
            line,
            maxsplit=1,
            flags=re.I,
        )[0]
        line = re.split(r"\s+\$\d", line, maxsplit=1)[0]
        line = re.split(r"\s+\d{1,2}\s+\$", line, maxsplit=1)[0]
        line = re.split(r"\s+PAYER'?S?\s*TIN\b", line, maxsplit=1, flags=re.I)[0]
        return line.strip(" ,;-")

    def _city_match(self, line: str) -> str | None:
        line = self._strip_box_noise(line)
        m = re.search(r"([A-Za-z .'-]+?),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)", line)
        if m and m.group(2).upper() in _US_STATES:
            return m.group(0)
        m = re.search(r"^(.*?)([A-Z]{2})\s*(\d{5}(?:-\d{4})?)$", line.strip(), flags=re.I)
        if m and m.group(2).upper() in _US_STATES and re.search(r"[A-Za-z]", m.group(1)):
            return f"{m.group(1).strip()}, {m.group(2).upper()} {m.group(3)}"
        return None

    def _norm_city(self, line: str) -> str | None:
        s = re.sub(
            r"^.*?(?:important tax information|This is important|tax information)\s+",
            "",
            line,
            flags=re.I,
        )
        s = re.sub(r"^tax information\s+", "", s, flags=re.I)
        m = self._city_match(s) or self._city_match(line) or s
        mm = re.search(r"^(.*?)([A-Z]{2})\s*(\d{5}(?:-\d{4})?)$", m.replace(",", " ").strip(), re.I)
        # reuse split
        s = m
        m2 = re.search(r"([A-Za-z .'-]+?),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)", s)
        if m2:
            return clean(f"{m2.group(1)}, {m2.group(2).upper()} {m2.group(3)}")
        m2 = re.search(r"^(.*?)([A-Z]{2})\s*(\d{5}(?:-\d{4})?)$", s.strip(), re.I)
        if m2 and m2.group(2).upper() in _US_STATES:
            return clean(f"{m2.group(1).strip()}, {m2.group(2).upper()} {m2.group(3)}")
        return clean(s)

    def _norm_street(self, raw: str) -> str | None:
        s = clean(raw)
        if not s:
            return None
        s = re.sub(r"\bPO\s*BOX\b", "PO BOX", s, flags=re.I)
        s = re.sub(r"\bP\.?\s*O\.?\s*BOX\b", "P.O. BOX", s, flags=re.I)
        s = re.sub(
            rf"^(\d+)([A-Za-z].*?)({_ST_SUFFIX})$",
            lambda m: f"{m.group(1)} {m.group(2)} {m.group(3)}".replace("  ", " "),
            s,
            flags=re.I,
        )
        s = re.sub(rf"([A-Za-z])({_ST_SUFFIX})$", r"\1 \2", s, flags=re.I)
        return clean(re.sub(r"\s+", " ", s))
