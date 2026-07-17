import time
import logging
from fastapi import FastAPI, UploadFile, File, Depends, Response, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from core.auth import verify_api_key, get_security_headers
from core.classifier import classify_document
from core.ocr_engine import extract_text_from_pdf
from core.parser import parse_extracted_text
from schemas.response import ExtractionResponse

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("robo-ocr-service")

app = FastAPI(
    title="ROBO1040 Custom OCR Extraction Service",
    description="API to classify and extract structured fields from tax documents.",
    version="1.0.0"
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust as needed in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers_middleware(request, call_next):
    """
    Middleware to append recommended security headers to all responses.
    """
    response = await call_next(request)
    headers = get_security_headers()
    for key, val in headers.items():
        response.headers[key] = val
    return response

@app.get("/health", status_code=status.HTTP_200_OK)
async def health():
    """
    Simple health check endpoint.
    """
    return {"status": "healthy", "timestamp": time.time()}

@app.post("/api/v1/extract", response_model=ExtractionResponse)
async def extract_fields(
    file: UploadFile = File(...),
    _api_key: str = Depends(verify_api_key)
):
    """
    Classifies the uploaded PDF document and extracts specific tax fields in JSON format.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF files are supported."
        )

    start_time = time.time()
    try:
        # Read file contents into memory
        pdf_bytes = await file.read()
        
        # 1. Extract text and layout metadata
        logger.info(f"Extracting text from document: {file.filename}")
        extracted_text_blocks, has_ocr_fallback = extract_text_from_pdf(pdf_bytes)
        
        # Compile all text lines for classification
        full_text = "\n".join([block["text"] for block in extracted_text_blocks])
        
        # 2. Classify document type
        logger.info("Classifying document type...")
        doc_type = classify_document(full_text)
        logger.info(f"Document classified as: {doc_type}")
        
        # 3. Parse fields based on document type
        logger.info(f"Parsing fields for {doc_type}...")
        parsed_data = parse_extracted_text(doc_type, extracted_text_blocks)
        
        processing_time = time.time() - start_time
        logger.info(f"Extraction completed in {processing_time:.2f} seconds.")
        
        # Calculate a mock/simple confidence score based on filled mandatory fields
        # (This can be refined per form type)
        confidence = 0.95 if doc_type != "Unknown" else 0.0
        
        return ExtractionResponse(
            document_type=doc_type,
            extracted_data=parsed_data,
            processing_time_seconds=processing_time,
            accuracy_estimate=confidence,
            ocr_fallback_used=has_ocr_fallback
        )
        
    except Exception as e:
        logger.error(f"Error during extraction: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal processing error: {str(e)}"
        )
