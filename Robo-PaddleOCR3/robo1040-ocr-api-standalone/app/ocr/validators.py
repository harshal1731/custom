"""Post-extraction field validation — format checks, boilerplate rejection."""

from __future__ import annotations

import re
from typing import Any

from app.ocr.field_engine import normalize_money

_TIN = re.compile(
    r"^(?:(?:\d{3}|X{3})-(?:\d{2}|X{2})-\d{4}|(?:\d{2}|X{2})-?\d{7}|\d{9})$",
    re.I,
)
_BOILERPLATE_NAME = re.compile(
    r"(?:furnished|required to file|nished to the IRS|important tax|"
    r"negligence|instructions|internal revenue|copy [abc]|"
    r"and\s+details|forms?\s*1099|total\s*relationship|edwardjones\.com|"
    r"independent\s*invest|mailing\s*address|account\s*name|"
    r"box\s*boxes|participant\s*copy|mamsa|annual\s*statement|"
    r"jefferson\s*city|healthequity|credit\s*union)\b",
    re.I,
)
_MONEY_KEY = re.compile(
    r"(?:interest|dividend|wage|withheld|compensation|penalty|premium|discount|"
    r"tax|amount|income|total|distribution|expense|paid|market|rollover|medicare|"
    r"social security)",
    re.I,
)


def _fix_tin(raw: str) -> str | None:
    s = raw.strip().upper().replace("*", "X")
    s = re.sub(r"\s+", "", s)
    m = re.search(r"((?:X{3}|\d{3})-(?:X{2}|\d{2})-\d{4})", s)
    if m:
        return m.group(1)
    m = re.search(r"(\d{2}-?\d{7})", s)
    if m:
        d = re.sub(r"\D", "", m.group(1))
        return f"{d[:2]}-{d[2:]}" if len(d) == 9 else None
    if _TIN.match(s):
        return s
    return None


def _clean_name(val: str) -> str | None:
    if not val or _BOILERPLATE_NAME.search(val):
        return None
    cleaned = val.strip()
    if len(cleaned) < 3:
        return None
    # Reject ultra-short OCR fragments like "LO E CWE" (all tokens tiny)
    words = [w for w in re.split(r"\s+", cleaned) if w]
    substantial = [w for w in words if len(re.sub(r"[^A-Za-z]", "", w)) >= 3]
    tiny = [w for w in words if len(re.sub(r"[^A-Za-z]", "", w)) <= 2]
    if len(words) >= 3 and len(substantial) < 2 and len(tiny) >= 2 and len(cleaned) < 14:
        return None
    return cleaned


def validate_fields(form_type: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Normalize formats and null out values that fail shape checks."""
    out: dict[str, Any] = dict(fields)
    for key, val in list(out.items()):
        if val is None or val == "":
            out[key] = None
            continue
        text = str(val).strip()
        kl = key.lower()

        if any(x in kl for x in ("tin", "ssn", "social security", " ein")):
            fixed = _fix_tin(text)
            out[key] = fixed
            continue

        if "name" in kl:
            out[key] = _clean_name(text)
            continue

        if "account" in kl:
            if re.search(
                r"5498|instructions|archer|msa|medicare|accourt|\(hsa\)|form\s*sa|"
                r"account\s*number|see\s*instruction",
                text,
                re.I,
            ):
                out[key] = None
            elif len(text) > 40:
                out[key] = None
            continue

        if _MONEY_KEY.search(kl):
            fixed = normalize_money(text)
            out[key] = fixed if fixed is not None else text
            continue

        if kl == "year" or key == "Year":
            m = re.search(r"\b(20\d{2})\b", text)
            out[key] = m.group(1) if m else None

    # 1099-DIV: ordinary dividends sometimes land in box 6 on EQ scans
    if form_type == "1099-DIV":
        if not out.get("1a Total ordinary dividends"):
            inv = out.get("6 Investment expenses")
            if inv and inv not in {"0.00", "0", None}:
                out["1a Total ordinary dividends"] = inv
                if not out.get("1b Qualified dividends") or out.get("1b Qualified dividends") in {
                    "0.00",
                    "0",
                }:
                    out["1b Qualified dividends"] = inv
                out["6 Investment expenses"] = "0.00"

    return out
