from typing import Any

from pydantic import BaseModel, Field


class ExtractResponse(BaseModel):
    form_type: str = Field(..., description="Detected tax form type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Form classification confidence")
    processing_ms: int
    page_count: int
    extraction_source: str = Field(
        default="paddle_ocr",
        description="Document load path: digital_pdf, paddleocr_vl, pp_structure, or paddle_ocr",
    )
    fields: dict[str, Any] = Field(
        ...,
        description="Key-value pairs extracted from the form (ROBO field name -> value)",
    )
    field_confidence: dict[str, float] = Field(
        default_factory=dict,
        description="Per-field confidence scores (0.0–1.0) after validation",
    )
    raw_text_preview: str | None = Field(
        default=None,
        description="First ~500 chars of OCR text for debugging",
    )


class HealthResponse(BaseModel):
    status: str
    paddleocr: bool
    pp_structure: bool = False
    paddleocr_vl: bool = False
    digital_pdf: bool = False
    schema_extract: bool = False
    app: str
