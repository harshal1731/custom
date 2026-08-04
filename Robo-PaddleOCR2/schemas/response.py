from pydantic import BaseModel, Field
from typing import Dict, Any

class ExtractionResponse(BaseModel):
    document_type: str = Field(..., description="Classified document type (e.g. W2, 1099-INT, etc.)")
    extracted_data: Dict[str, Any] = Field(..., description="Key-value pairs of extracted form fields")
    processing_time_seconds: float = Field(..., description="Time taken to process request")
    ocr_fallback_used: bool = Field(..., description="Indicates if image rendering and OCR was required")
