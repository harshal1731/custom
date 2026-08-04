from __future__ import annotations

import time

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from app.auth import require_api_key
from app.config import get_settings
from app.ocr.pipeline import process_pdf
from app.schemas.response import ExtractResponse, HealthResponse
from app.security import SecurityHeadersMiddleware

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Custom OCR API for ROBO1040 tax forms (PyMuPDF + PP-StructureV3 + KIE). "
        "Upload a PDF and receive structured key-value JSON fields."
    ),
    version="2.1.0",
)

origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)


@app.on_event("startup")
def startup_warmup() -> None:
    try:
        from app.ocr.engine import warmup_ocr

        warmup_ocr()
    except Exception:
        pass
    # PP-StructureV3 loads lazily on first scanned PDF — no startup warmup.


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    paddle_ok = False
    structure_ok = False
    vl_ok = False
    digital_ok = False
    try:
        from app.ocr.engine import get_ocr

        get_ocr()
        paddle_ok = True
    except Exception:
        paddle_ok = False
    try:
        import fitz  # noqa: F401

        digital_ok = True
    except Exception:
        digital_ok = False
    if get_settings().use_pp_structure:
        try:
            from app.ocr.structure import structure_models_cached

            structure_ok = structure_models_cached()
        except Exception:
            structure_ok = False
    if get_settings().use_paddleocr_vl:
        try:
            from app.ocr.paddleocr_vl import paddleocr_vl_available, vl_models_cached

            vl_ok = paddleocr_vl_available() and vl_models_cached()
        except Exception:
            vl_ok = False
    return HealthResponse(
        status="ok",
        paddleocr=paddle_ok,
        pp_structure=structure_ok,
        paddleocr_vl=vl_ok,
        digital_pdf=digital_ok,
        schema_extract=get_settings().use_schema_extract,
        app=settings.app_name,
    )


@app.post(
    "/api/v1/extract",
    response_model=ExtractResponse,
    tags=["ocr"],
    summary="Extract key-value fields from a tax-form PDF",
)
async def extract(
    file: UploadFile = File(..., description="PDF tax form"),
    _: str = Depends(require_api_key),
) -> ExtractResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported.",
        )

    content_type = (file.content_type or "").lower()
    if content_type and content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported content type: {content_type}",
        )

    pdf_bytes = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(pdf_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.max_upload_mb} MB limit.",
        )
    if not pdf_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file.")

    started = time.perf_counter()
    try:
        classification, doc, fields, field_confidence = process_pdf(pdf_bytes)
        ocr = doc.ocr
    except Exception as exc:  # noqa: BLE001 - return clean API error
        msg = str(exc)
        low = msg.lower()
        if "poppler" in low or "pdfinfo" in low:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Poppler is not installed (or not on PATH). "
                    "Scanned/image PDFs need Poppler on Windows. "
                    "1) Download poppler for Windows from "
                    "https://github.com/oschwartz10612/poppler-windows/releases "
                    "2) Unzip it  3) Add the Library\\bin folder to your system PATH "
                    "4) Restart the API (close run_*.bat and start again). "
                    "Digital/text PDFs can work without Poppler via PyMuPDF."
                ),
            ) from exc
        import traceback

        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail=f"OCR processing failed: {exc}\n\n{tb}",
        ) from exc

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    preview = ocr.full_text.strip().replace("\n", " ")
    if len(preview) > 500:
        preview = preview[:500] + "..."

    return ExtractResponse(
        form_type=classification.form_type,
        confidence=classification.confidence,
        processing_ms=elapsed_ms,
        page_count=ocr.page_count,
        extraction_source=doc.source,
        fields=fields,
        field_confidence=field_confidence,
        raw_text_preview=preview or None,
    )
