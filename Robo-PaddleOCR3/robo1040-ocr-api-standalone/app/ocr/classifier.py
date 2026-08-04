from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Classification:
    form_type: str
    confidence: float


import re

# Order matters for tie-breakers; brokerage checked with boost when composite markers exist.
RULES: list[tuple[str, list[str], float]] = [
    (
        "W-2",
        [
            r"form\s*w-?2",
            r"fom\s*w-?2",
            r"fonn\s*w-?2",
            r"wv-?2",
            r"wage\s*and\s*tax\s*statement",
            r"wag6\s*and\s*tax\s*stat",
            r"wages,?\s*tips,?\s*other\s*comp",
            # Avoid bare "employer identification number" — 5498 instructions mention it
            r"employer\s*identification\s*number\s*\(?\s*ein",
            r"social\s*security\s*wages",
        ],
        1.0,
    ),
    (
        "5498-SA",
        [
            r"form\s*5498-?sa",
            r"5498-?sa",
            r"5498\s*sa",
            r"hsa,?\s*archer\s*msa",
            r"fair\s*market\s*value\s*of\s*hsa",
            r"participant",
            r"trustee'?s?\s*(?:or\s*issuer'?s?\s*)?(?:name|tin|federal)",
        ],
        1.0,
    ),
    (
        "1099-INT",
        [
            r"form\s*1099-?int",
            r"1099-?int",
            r"1099\s*int",
            r"interest\s*income",
            r"early\s*withdrawal\s*penalty",
            r"payer'?s\s*rtn",
        ],
        1.0,
    ),
    (
        "1099-DIV",
        [
            r"form\s*1099-?(?:div|dn)",
            r"1099-?(?:div|dn)",
            r"1099\s*(?:div|dn)",
            r"total\s*ordinary\s*dividends?",
            r"qualified\s*dividends?",
            r"section\s*199a\s*dividends?",
        ],
        1.0,
    ),
    (
        "Consolidated Brokerage Statement",
        [
            r"form\s*1099\s*composite",
            r"1099\s*composite",
            r"year-?end\s*summary",
            r"consolidated\s*1099",
            r"brokerage\s*statement",
            r"1099-?b\b",
            r"cost\s*basis",
            r"edward\s*jones",
            r"fidelity",
            r"charles\s*schwab",
            r"schwab\b",
            r"ameritrade",
            r"morgan\s*stanley",
            r"tax\s*reporting\s*statement",
            r"portfolio\s*summary",
            r"account\s*summary",
            r"raymond\s*james",
        ],
        1.2,
    ),
]


_SA_STRONG = [
    r"5498-?sa",
    r"form\s*5498",
    r"hsa,?\s*archer\s*msa",
    r"fair\s*market\s*value\s*of\s*hsa",
    r"medicare\s*advantage\s*msa",
    r"copy\s*b\s*for\s*participant",
]

_BROKERAGE_STRONG = [
    r"1099\s*composite",
    r"year-?end\s*summary",
    r"tax\s*reporting\s*statement",
    r"consolidated\s*1099",
    r"brokerage\s*statement",
    r"edward\s*jones",
    r"fidelity\s*investments",
    r"charles\s*schwab",
    r"morgan\s*stanley",
    r"raymond\s*james",
    r"ameriprise",
]


def classify_form(ocr_text: str) -> Classification:
    # Use spaces for regex, replace newlines with space
    text = " ".join(ocr_text.split()).lower()

    # Strong 5498 override — instructions mention "Form W-2" and would otherwise tie
    if any(re.search(pat, text) for pat in _SA_STRONG):
        return Classification(form_type="5498-SA", confidence=0.99)

    # Strong brokerage override — composites embed 1099-DIV/INT sections
    if any(re.search(pat, text) for pat in _BROKERAGE_STRONG):
        return Classification(form_type="Consolidated Brokerage Statement", confidence=0.99)

    scores: dict[str, float] = {}
    hit_counts: dict[str, int] = {}
    for form_type, patterns, weight in RULES:
        hits = 0
        for pat in patterns:
            if re.search(pat, text):
                hits += 1
        if hits:
            hit_counts[form_type] = hits
            # Require fewer hits for a good score to be resilient to OCR failure
            divisor = 2.0 if len(patterns) > 2 else float(len(patterns))
            scores[form_type] = min(1.0, hits / divisor) * weight

    if not scores:
        return Classification(form_type="Unknown", confidence=0.0)

    # Prefer more pattern hits on score ties (avoids W-2 winning 5498 ties)
    best = max(scores.items(), key=lambda x: (x[1], hit_counts.get(x[0], 0)))
    return Classification(form_type=best[0], confidence=round(min(best[1], 1.0), 3))
