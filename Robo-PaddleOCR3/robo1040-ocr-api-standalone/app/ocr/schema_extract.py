"""Schema-driven field extraction for tax forms.

Maps document text/markdown into ROBO FieldSpec keys using:
1. Deterministic label/box/value rules (always on, offline)
2. Optional local OpenAI-compatible LLM (Ollama / vLLM) for hard layouts

No issuer hardcoding — schemas use IRS field labels only.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.config import get_settings
from app.ocr.field_engine import FieldSpec, normalize_money
from app.ocr.form_specs import get_field_specs
from app.ocr.types import KiePair, OcrResult

logger = logging.getLogger(__name__)

_MONEY = re.compile(
    r"(?:\$\s*)?-?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}"
)
_SSN = re.compile(r"(?:X{3}|x{3}|\*{3}|\d{3})-(?:X{2}|x{2}|\*{2}|\d{2})-\d{4}")
_EIN = re.compile(r"\d{2}-\d{7}")
_YEAR = re.compile(r"\b(20\d{2})\b")
_ACCOUNT = re.compile(r"\b([A-Z0-9]{4,}[-A-Z0-9]{0,20})\b")

_LABEL_MEMORY: dict[str, Any] | None = None


def load_label_memory() -> dict[str, Any]:
    """Load mined label examples (from scripts/vl/train_from_labels.py)."""
    global _LABEL_MEMORY
    if _LABEL_MEMORY is not None:
        return _LABEL_MEMORY
    settings = get_settings()
    path = settings.label_memory_path
    _LABEL_MEMORY = {}
    if not path:
        return _LABEL_MEMORY
    from pathlib import Path

    p = Path(path)
    if not p.is_file():
        # try repo-relative
        alt = Path(__file__).resolve().parents[2] / path
        p = alt if alt.is_file() else p
    if p.is_file():
        try:
            _LABEL_MEMORY = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load label memory: %s", exc)
            _LABEL_MEMORY = {}
    return _LABEL_MEMORY


def few_shot_examples(form_type: str, limit_per_field: int = 2) -> dict[str, list[str]]:
    mem = load_label_memory()
    forms = mem.get("forms") or {}
    fields = forms.get(form_type) or {}
    return {k: list(v)[:limit_per_field] for k, v in fields.items() if v}


def schema_for_form(form_type: str) -> dict[str, Any]:
    """JSON-schema-like dict describing expected ROBO fields."""
    specs = get_field_specs(form_type)
    properties: dict[str, Any] = {}
    for spec in specs:
        properties[spec.key] = {
            "type": "string",
            "value_type": spec.value_type,
            "labels": list(spec.labels),
            "box": spec.box,
            "role": spec.role,
            "part": spec.part,
        }
    return {
        "form_type": form_type,
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _find_after_label(text: str, labels: list[str], value_type: str) -> str | None:
    for label in labels:
        ln = re.escape(label)
        window = rf"{ln}.{{0,120}}"
        chunk_m = re.search(window, text, flags=re.I | re.DOTALL)
        if not chunk_m:
            continue
        chunk = chunk_m.group(0)
        if value_type == "money":
            m = _MONEY.search(chunk)
            if m:
                return normalize_money(m.group(0))
        elif value_type == "tin_ssn":
            m = _SSN.search(chunk)
            if m:
                return m.group(0)
        elif value_type == "tin_ein":
            m = _EIN.search(chunk)
            if m:
                return m.group(0)
        elif value_type == "year":
            m = _YEAR.search(chunk)
            if m:
                return m.group(1)
        elif value_type == "account":
            # Prefer digits-heavy tokens after label
            after = text[chunk_m.end() : chunk_m.end() + 80]
            m = re.search(r"([A-Z0-9][\w-]{3,24})", after, re.I)
            if m:
                return m.group(1)
        else:
            after = text[chunk_m.end() : chunk_m.end() + 100]
            line = after.split("\n", 1)[0].strip(" :|\t")
            if line and len(line) >= 2:
                return line[:200]
    return None


def _find_by_box(text: str, box: str, value_type: str) -> str | None:
    if not box:
        return None
    # e.g. "1 Wages..." or "Box 1" then money
    patterns = [
        rf"(?:^|[\s|]){re.escape(box)}(?:\s|[.|:)>-])+({_MONEY.pattern})",
        rf"(?:box\s*)?{re.escape(box)}\b.{{0,60}}?({_MONEY.pattern})",
    ]
    if value_type != "money":
        return None
    for pat in patterns:
        m = re.search(pat, text, flags=re.I | re.MULTILINE | re.DOTALL)
        if m:
            return normalize_money(m.group(1))
    return None


def extract_schema_rules(form_type: str, text: str) -> dict[str, Any]:
    """Deterministic schema fill from OCR/VL text."""
    specs = get_field_specs(form_type)
    out: dict[str, Any] = {}
    if not text.strip():
        return out

    for spec in specs:
        if spec.value_type == "address_block":
            continue  # roles handled by SpatialFieldEngine
        val = None
        if spec.labels:
            val = _find_after_label(text, spec.labels, spec.value_type)
        if val is None and spec.box:
            val = _find_by_box(text, spec.box, spec.value_type)
        if val is None and spec.value_type == "year":
            m = _YEAR.search(text)
            val = m.group(1) if m else None
        if val is not None and str(val).strip():
            out[spec.key] = str(val).strip()
    return out


def _llm_schema_prompt(form_type: str, document_text: str) -> str:
    schema = schema_for_form(form_type)
    keys = list(schema["properties"].keys())
    examples = few_shot_examples(form_type)
    return (
        "Extract US tax form fields as JSON only. Use null for missing values.\n"
        "Do not invent values. Use IRS box labels. No issuer-specific rules.\n"
        f"form_type: {form_type}\n"
        f"fields: {json.dumps(keys)}\n"
        f"example_values_from_training: {json.dumps(examples)}\n"
        f"document:\n{document_text[:12000]}\n"
        "Respond with a single JSON object mapping field name -> string|null."
    )


def extract_schema_llm(form_type: str, document_text: str) -> dict[str, Any]:
    """Optional local LLM schema fill (Ollama / OpenAI-compatible)."""
    settings = get_settings()
    base = (settings.schema_llm_base_url or "").rstrip("/")
    model = settings.schema_llm_model
    if not base or not model or not document_text.strip():
        return {}

    url = f"{base}/chat/completions"
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "You extract tax form fields as JSON only."},
            {"role": "user", "content": _llm_schema_prompt(form_type, document_text)},
        ],
        "response_format": {"type": "json_object"},
    }
    try:
        with httpx.Client(timeout=settings.schema_llm_timeout_s) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return {}
        allowed = {s.key for s in get_field_specs(form_type)}
        return {
            k: (None if v in ("", "null", "None") else str(v))
            for k, v in parsed.items()
            if k in allowed
        }
    except Exception as exc:
        logger.warning("Schema LLM extraction failed: %s", exc)
        return {}


def merge_schema_fields(
    fields: dict[str, Any],
    schema_fields: dict[str, Any],
    form_type: str,
) -> dict[str, Any]:
    """Fill missing / invalid fields from schema extraction."""
    if not schema_fields:
        return fields
    specs = {s.key: s for s in get_field_specs(form_type)}
    out = dict(fields)

    for key, val in schema_fields.items():
        if val is None or str(val).strip() == "":
            continue
        current = out.get(key)
        if current in (None, ""):
            out[key] = val
            continue
        spec = specs.get(key)
        if not spec:
            continue
        # Upgrade if current fails type shape and schema value looks better
        cur_s, new_s = str(current), str(val)
        if spec.value_type == "money":
            if normalize_money(cur_s) is None and normalize_money(new_s) is not None:
                out[key] = normalize_money(new_s)
        elif spec.value_type == "tin_ssn" and not _SSN.fullmatch(cur_s) and _SSN.fullmatch(new_s):
            out[key] = new_s
        elif spec.value_type == "tin_ein" and not _EIN.fullmatch(cur_s) and _EIN.fullmatch(new_s):
            out[key] = new_s
    return out


def schema_fields_to_kie_pairs(schema_fields: dict[str, Any], method: str = "schema") -> list[KiePair]:
    pairs: list[KiePair] = []
    for key, val in schema_fields.items():
        if val is None or str(val).strip() == "":
            continue
        pairs.append(
            KiePair(
                field_key=key,
                label=key,
                value=str(val),
                confidence=0.88 if method == "schema_llm" else 0.82,
                method=method,
            )
        )
    return pairs


def run_schema_extraction(form_type: str, ocr: OcrResult) -> dict[str, Any]:
    """Run rule schema fill (+ optional local LLM) against OCR/VL text."""
    settings = get_settings()
    if not settings.use_schema_extract:
        return {}

    markdown = getattr(ocr, "markdown", None) or ""
    text = markdown if isinstance(markdown, str) and markdown.strip() else ocr.full_text
    rules = extract_schema_rules(form_type, text)

    llm_fields: dict[str, Any] = {}
    if settings.schema_llm_base_url and settings.schema_llm_model:
        llm_fields = extract_schema_llm(form_type, text)

    # LLM fills gaps; rules win on typed conflicts when both present
    merged = dict(llm_fields)
    merged.update({k: v for k, v in rules.items() if v not in (None, "")})
    return merged
