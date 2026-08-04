"""Shared pure helpers (no issuer/person literals). Prefer field_engine for extraction."""

from __future__ import annotations

from app.ocr.field_engine import (
    FieldSpec,
    SpatialFieldEngine,
    clean,
    format_ein,
    format_ssn,
    normalize_money,
    result_from_text,
)

__all__ = [
    "FieldSpec",
    "SpatialFieldEngine",
    "clean",
    "format_ein",
    "format_ssn",
    "normalize_money",
    "result_from_text",
]
