"""PyMuPDF text-layer extraction for digital PDFs (<1s, perfect coordinates).

Includes quality detection: if the text layer is garbled (spaced characters,
single-letter tokens), the pipeline will fall back to image-based OCR.
"""

from __future__ import annotations

import logging
import re

import fitz

from app.ocr.types import OcrPage, OcrResult, OcrToken

logger = logging.getLogger(__name__)


def _group_lines(tokens: list[OcrToken], y_tol: int = 4, max_gap: int = 40) -> list[str]:
    if not tokens:
        return []
    ordered = sorted(tokens, key=lambda t: (t.top, t.left))
    lines: list[list[OcrToken]] = []
    current: list[OcrToken] = []
    current_y: float | None = None
    for tok in ordered:
        if current_y is None or abs(tok.cy - current_y) <= y_tol:
            if current and (tok.left - current[-1].right) > max_gap:
                lines.append(sorted(current, key=lambda t: t.left))
                current = [tok]
                current_y = tok.cy
            else:
                current.append(tok)
                current_y = tok.cy if current_y is None else (current_y * 0.7 + tok.cy * 0.3)
        else:
            lines.append(sorted(current, key=lambda t: t.left))
            current = [tok]
            current_y = tok.cy
    if current:
        lines.append(sorted(current, key=lambda t: t.left))
    return [" ".join(t.text for t in line) for line in lines]



def is_digital_pdf(pdf_bytes: bytes, min_chars: int = 200, max_pages: int = 3) -> bool:
    """True when PDF has a usable embedded text layer (not scan-only)."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return False
    total = 0
    limit = min(len(doc), max_pages)
    for idx in range(limit):
        total += len(doc[idx].get_text("text").strip())
        if total >= min_chars:
            return True
    return False


def text_quality_score(pdf_bytes: bytes, max_pages: int = 1) -> float:
    """Measure text layer quality. Returns fraction of single-char "words".

    A high score (> 0.30) indicates spaced-character text where each letter
    is positioned individually — e.g. "B A D  B U N N I E S".
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return 1.0  # assume bad quality on error

    total_words = 0
    single_char_words = 0
    limit = min(len(doc), max_pages)

    for idx in range(limit):
        words = doc[idx].get_text("words")
        for w in words:
            if len(w) < 5:
                continue
            text = str(w[4]).strip()
            if not text:
                continue
            total_words += 1
            if len(text) == 1 and text.isalpha():
                single_char_words += 1

    if total_words == 0:
        return 1.0
    return single_char_words / total_words


def is_blank_form_shell(pdf_bytes: bytes, max_pages: int = 1) -> bool:
    """True when text layer is an unfilled IRS template (labels, no money values).

    Blank digital shells look "high quality" but contain no extractable amounts,
    so the pipeline should fall through to image OCR.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return False
    limit = min(len(doc), max_pages)
    text = "\n".join(doc[idx].get_text("text") for idx in range(limit))
    if len(text.strip()) < 80:
        return False
    # Real money only (require cents) — avoid counting OMB Nos / years as amounts
    money_hits = len(re.findall(r"\$\s*\d{1,3}(?:,\d{3})*\.\d{2}\b", text))
    money_hits += len(re.findall(r"\b\d{1,3}(?:,\d{3})*\.\d{2}\b", text))
    tin_hits = len(
        re.findall(
            r"\b(?:\d{3}-\d{2}-\d{4}|\d{2}-\d{7}|X{3}-X{2}-\d{4})\b",
            text,
            re.I,
        )
    )
    # Person-like filled lines (not just labels)
    person_hits = len(
        re.findall(
            r"(?m)^[A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+\s*$",
            text,
        )
    )
    formish = bool(
        re.search(
            r"\b(?:form\s*w-?2|1099-?(?:int|div|sa)|5498-?sa|wage\s*and\s*tax|"
            r"recipient'?s?\s*name|employee'?s?\s*name)\b",
            text,
            re.I,
        )
    )
    return formish and money_hits == 0 and tin_hits == 0 and person_hits == 0


def _collapse_spaced_tokens(tokens: list[OcrToken], gap_threshold: int = 15) -> list[OcrToken]:
    """Merge adjacent single-character tokens into proper words.

    When a PDF has spaced characters (each letter is a separate word),
    this function detects tokens that are close together on the same line
    and merges them into multi-character tokens.
    """
    if not tokens:
        return tokens

    # Sort by line position, then left edge
    ordered = sorted(tokens, key=lambda t: (t.top, t.left))

    merged: list[OcrToken] = []
    current_group: list[OcrToken] = [ordered[0]]

    for tok in ordered[1:]:
        last = current_group[-1]
        same_line = abs(tok.cy - last.cy) <= 6
        close = (tok.left - last.right) <= gap_threshold

        if same_line and close and (len(last.text) <= 2 or len(tok.text) <= 2):
            current_group.append(tok)
        else:
            # Emit merged token
            merged.append(_merge_token_group(current_group))
            current_group = [tok]

    if current_group:
        merged.append(_merge_token_group(current_group))

    return merged


def _merge_token_group(group: list[OcrToken]) -> OcrToken:
    """Merge a group of tokens into a single token."""
    if len(group) == 1:
        return group[0]

    text = "".join(t.text for t in group)
    avg_conf = sum(t.confidence for t in group) / len(group)

    return OcrToken(
        text=text,
        confidence=avg_conf,
        left=min(t.left for t in group),
        top=min(t.top for t in group),
        right=max(t.right for t in group),
        bottom=max(t.bottom for t in group),
    )


def extract_digital_pdf(pdf_bytes: bytes, max_pages: int = 1) -> OcrResult:
    """Extract word-level tokens with coordinates from PDF text layer.

    Detects spaced-character PDFs and collapses single-letter tokens
    into proper words automatically.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: list[OcrPage] = []
    limit = min(len(doc), max_pages)

    # Check quality to decide if we need token collapsing
    quality = text_quality_score(pdf_bytes, max_pages=limit)
    needs_collapse = quality > 0.25
    if needs_collapse:
        logger.info("Spaced-character PDF detected (quality=%.2f), collapsing tokens", quality)

    for idx in range(limit):
        page = doc[idx]
        rect = page.rect
        words = page.get_text("words")
        tokens: list[OcrToken] = []
        for w in words:
            if len(w) < 5:
                continue
            x0, y0, x1, y1, word = w[0], w[1], w[2], w[3], w[4]
            text = str(word).strip()
            if not text:
                continue
            tokens.append(
                OcrToken(
                    text=text,
                    confidence=1.0,
                    left=int(x0),
                    top=int(y0),
                    right=int(x1),
                    bottom=int(y1),
                )
            )

        # Collapse spaced characters into real words
        if needs_collapse:
            tokens = _collapse_spaced_tokens(tokens)

        lines = _group_lines(tokens)
        text = "\n".join(lines)

        pages.append(
            OcrPage(
                page_number=idx + 1,
                text=text,
                lines=lines,
                tokens=tokens,
                width=int(rect.width),
                height=int(rect.height),
            )
        )
    return OcrResult(pages=pages, source="digital_pdf")
