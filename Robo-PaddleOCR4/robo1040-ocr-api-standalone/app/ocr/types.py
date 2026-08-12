"""Lightweight OCR data types (no native/PDF dependencies)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

DocumentSource = Literal["digital_pdf", "paddleocr_vl", "pp_structure", "paddle_ocr"]


@dataclass
class OcrToken:
    text: str
    confidence: float
    left: int
    top: int
    right: int
    bottom: int

    @property
    def cx(self) -> float:
        return (self.left + self.right) / 2

    @property
    def cy(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass
class LayoutRegion:
    """Layout block from PP-StructureV3 or synthetic grouping."""

    label: str
    left: int
    top: int
    right: int
    bottom: int
    score: float = 1.0

    @property
    def cx(self) -> float:
        return (self.left + self.right) / 2

    @property
    def cy(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass
class KiePair:
    """Label → value pair (spatial KIE or VI-LayoutXLM output)."""

    field_key: str
    label: str
    value: str
    confidence: float
    method: str = "spatial"


@dataclass
class OcrPage:
    page_number: int
    text: str
    lines: list[str]
    tokens: list[OcrToken] = field(default_factory=list)
    width: int = 0
    height: int = 0
    layout_regions: list[LayoutRegion] = field(default_factory=list)


@dataclass
class OcrResult:
    pages: list[OcrPage]
    source: DocumentSource = "paddle_ocr"
    kie_pairs: list[KiePair] = field(default_factory=list)
    markdown: str = ""

    @property
    def full_text(self) -> str:
        return "\n".join(p.text for p in self.pages)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def layout_regions(self) -> list[LayoutRegion]:
        regions: list[LayoutRegion] = []
        for page in self.pages:
            regions.extend(page.layout_regions)
        return regions


@dataclass
class DocumentLoadResult:
    ocr: OcrResult
    source: DocumentSource
    is_digital: bool
    kie_pairs: list[KiePair] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
