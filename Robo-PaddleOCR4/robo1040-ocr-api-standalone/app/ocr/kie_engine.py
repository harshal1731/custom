"""Layout-aware KIE: spatial label→value pairing + optional VI-LayoutXLM models."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.ocr.field_engine import SpatialFieldEngine, normalize_money
from app.ocr.form_specs import get_field_specs
from app.ocr.types import KiePair, LayoutRegion, OcrResult, OcrToken

_MONEY = re.compile(r"^(?:\$\s*)?-?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}$")
_SSN = re.compile(r"^(?:X{3}|x{3}|\*{3}|\d{3})-(?:X{2}|x{2}|\*{2}|\d{2})-\d{4}$")
_EIN = re.compile(r"^(?:\d{2}-\d{7}|\d{9})$")
_YEAR = re.compile(r"^20\d{2}$")


def _norm_label(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _label_match(token_text: str, labels: list[str]) -> bool:
    norm = _norm_label(token_text)
    if not norm:
        return False
    for label in labels:
        ln = _norm_label(label)
        if ln and (ln in norm or norm in ln):
            return True
    return False


def _region_for_token(token: OcrToken, regions: list[LayoutRegion]) -> LayoutRegion | None:
    best: LayoutRegion | None = None
    best_area = float("inf")
    for region in regions:
        if (
            token.left >= region.left - 8
            and token.right <= region.right + 8
            and token.top >= region.top - 8
            and token.bottom <= region.bottom + 8
        ):
            area = (region.right - region.left) * (region.bottom - region.top)
            if area < best_area:
                best = region
                best_area = area
    return best


def _tokens_in_region(tokens: list[OcrToken], region: LayoutRegion) -> list[OcrToken]:
    return [
        t
        for t in tokens
        if t.cx >= region.left - 4
        and t.cx <= region.right + 4
        and t.cy >= region.top - 4
        and t.cy <= region.bottom + 4
    ]


def _value_shape_ok(value_type: str, text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if value_type == "money":
        return bool(_MONEY.match(t.replace("$", "").replace(",", "")) or _MONEY.match(t))
    if value_type == "tin_ssn":
        return bool(_SSN.match(t))
    if value_type == "tin_ein":
        return bool(_EIN.match(t))
    if value_type == "year":
        return bool(_YEAR.match(t))
    return len(t) >= 1


def _find_spatial_value(
    label_token: OcrToken,
    candidates: list[OcrToken],
    value_type: str,
) -> tuple[str | None, float]:
    """Find value to the right or below label (VI-LayoutXLM RE surrogate)."""
    right: list[OcrToken] = []
    below: list[OcrToken] = []
    for tok in candidates:
        if tok is label_token:
            continue
        same_line = abs(tok.cy - label_token.cy) <= max(12, (label_token.bottom - label_token.top) * 0.8)
        if same_line and tok.left >= label_token.right - 4:
            right.append(tok)
        elif tok.top >= label_token.bottom - 4 and abs(tok.cx - label_token.cx) <= 200:
            below.append(tok)

    for group, base_conf in ((right, 0.92), (below, 0.85)):
        ordered = sorted(group, key=lambda t: (t.left, t.top))
        for tok in ordered:
            if _value_shape_ok(value_type, tok.text):
                conf = base_conf * tok.confidence
                if value_type == "money":
                    return normalize_money(tok.text), conf
                return tok.text.strip(), conf

    # Multi-token money to the right on same line
    if value_type == "money" and right:
        ordered = sorted(right, key=lambda t: t.left)
        joined = " ".join(t.text for t in ordered[:3])
        m = re.search(r"((?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})", joined)
        if m:
            return normalize_money(m.group(1)), 0.78
    return None, 0.0


def extract_spatial_kie(ocr: OcrResult, form_type: str) -> list[KiePair]:
    """Build label→value pairs using layout regions + spatial relations."""
    specs = get_field_specs(form_type)
    if not specs or not ocr.pages:
        return []

    page = ocr.pages[0]
    tokens = page.tokens
    regions = page.layout_regions
    if not tokens:
        return []

    pairs: list[KiePair] = []
    used_values: set[str] = set()

    for spec in specs:
        if spec.value_type == "address_block":
            continue
        if not spec.labels and not spec.box:
            continue

        label_tokens = [t for t in tokens if spec.labels and _label_match(t.text, spec.labels)]
        if spec.box:
            box_tokens = [
                t
                for t in tokens
                if t.text.strip() == spec.box or re.fullmatch(rf"{re.escape(spec.box)}[\s.:|)]*", t.text.strip())
            ]
            label_tokens = label_tokens or box_tokens

        best_val: str | None = None
        best_conf = 0.0

        for lt in label_tokens:
            region = _region_for_token(lt, regions) if regions else None
            pool = _tokens_in_region(tokens, region) if region else tokens
            val, conf = _find_spatial_value(lt, pool, spec.value_type)
            if val and conf > best_conf and val not in used_values:
                best_val, best_conf = val, conf

        if best_val and best_conf >= 0.7:
            pairs.append(
                KiePair(
                    field_key=spec.key,
                    label=spec.labels[0] if spec.labels else spec.key,
                    value=best_val,
                    confidence=best_conf,
                    method="spatial",
                )
            )
            used_values.add(best_val)

    return pairs


def _try_vi_layoutxlm_kie(ocr: OcrResult, form_type: str) -> list[KiePair]:
    """Optional VI-LayoutXLM SER/RE when fine-tuned model dirs are configured."""
    settings = get_settings()
    ser_dir = settings.kie_ser_model_dir
    if not ser_dir or not Path(ser_dir).exists():
        return []

    # Fine-tuned models are invoked via PaddleOCR ppstructure scripts (see scripts/kie/).
    # Runtime hook: if a serialized predictions JSON exists next to the model, load it.
    pred_file = Path(ser_dir) / "latest_predictions.json"
    if not pred_file.exists():
        return []

    try:
        data = json.loads(pred_file.read_text(encoding="utf-8"))
    except Exception:
        return []

    pairs: list[KiePair] = []
    for item in data.get("pairs", []):
        key = item.get("field_key") or item.get("key")
        val = item.get("value")
        if key and val:
            pairs.append(
                KiePair(
                    field_key=str(key),
                    label=str(item.get("label") or key),
                    value=str(val),
                    confidence=float(item.get("confidence") or 0.9),
                    method="vi_layoutxlm",
                )
            )
    return pairs


def run_kie(ocr: OcrResult, form_type: str) -> list[KiePair]:
    settings = get_settings()
    if not settings.use_kie:
        return []

    spatial = extract_spatial_kie(ocr, form_type)
    if settings.kie_ser_model_dir:
        model_pairs = _try_vi_layoutxlm_kie(ocr, form_type)
        if model_pairs:
            by_key = {p.field_key: p for p in spatial}
            for mp in model_pairs:
                if mp.confidence >= by_key.get(mp.field_key, KiePair("", "", "", 0.0)).confidence:
                    by_key[mp.field_key] = mp
            return list(by_key.values())
    return spatial


def merge_kie_fields(
    fields: dict[str, Any],
    pairs: list[KiePair],
    form_type: str,
) -> dict[str, Any]:
    """Fill missing fields or upgrade low-confidence extractions with KIE pairs."""
    if not pairs:
        return fields

    out = dict(fields)
    specs = {s.key: s for s in get_field_specs(form_type)}

    label_noise = re.compile(
        r"(?:Statutory|Retirement|Third-party|Dependent|Nonqualified|Allocated|Local|Locality|Wages|Statement|Treasury|IRS|14Other|12b|12c|12d)",
        re.I,
    )

    for pair in pairs:
        spec = specs.get(pair.field_key)
        val = str(pair.value).strip()
        if not val or label_noise.search(val):
            continue
        if spec and not _value_shape_ok(spec.value_type, val):
            continue

        current = out.get(pair.field_key)
        if current is not None and str(current).strip():
            if spec and spec.value_type in {"money", "tin_ssn", "tin_ein", "year"}:
                if not _value_shape_ok(spec.value_type, str(current)) and _value_shape_ok(
                    spec.value_type, val
                ):
                    out[pair.field_key] = val
            continue

        if pair.field_key not in out or out[pair.field_key] is None:
            out[pair.field_key] = val

    return out



def enhance_with_spatial_engine(
    ocr: OcrResult,
    form_type: str,
    fields: dict[str, Any],
) -> dict[str, Any]:
    """Second pass: use SpatialFieldEngine for roles/addresses KIE cannot resolve."""
    if form_type == "W-2":
        return fields
    specs = get_field_specs(form_type)
    if not specs:
        return fields

    eng = SpatialFieldEngine.from_ocr(ocr, prefer_left_half=(form_type == "W-2"))
    spatial = eng.extract(specs)
    out = dict(fields)
    for key, val in spatial.items():
        if out.get(key) in (None, "") and val not in (None, ""):
            out[key] = val
    return out

