import os
import fitz  # PyMuPDF
import logging
from PIL import Image
import io

logger = logging.getLogger("robo-ocr-service")

# Global PaddleOCR instance placeholder
_paddle_ocr_instance = None

def get_paddle_ocr():
    """
    Get or initialize the PaddleOCR instance dynamically, with error tolerance.
    """
    global _paddle_ocr_instance
    if _paddle_ocr_instance is not None:
        return _paddle_ocr_instance

    try:
        from paddleocr import PaddleOCR
        # Initialize PaddleOCR with basic language parameter to avoid argument mismatch
        _paddle_ocr_instance = PaddleOCR(lang='en')
        logger.info("PaddleOCR successfully initialized.")
        return _paddle_ocr_instance
    except Exception as e:
        logger.warning(f"PaddleOCR failed to initialize: {e}. Falling back to PyMuPDF only.")
        return None

def extract_text_from_pdf(pdf_bytes: bytes) -> tuple[list[dict], bool]:
    """
    Extracts text from PDF bytes.
    First tries direct PDF text extraction. If too little text is found, 
    renders PDF pages to images and runs PaddleOCR.
    
    Returns:
        (blocks, ocr_fallback_used):
        - blocks: list of dicts, each with {x0, y0, x1, y1, text, page}
        - ocr_fallback_used: bool indicating if OCR was used
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    blocks = []
    
    # 1. Attempt Direct PyMuPDF extraction first
    direct_extracted_char_count = 0
    for page_idx, page in enumerate(doc):
        page_blocks = page.get_text("blocks")
        for b in page_blocks:
            x0, y0, x1, y1, text, block_no, block_type = b
            clean_text = text.strip()
            if clean_text:
                direct_extracted_char_count += len(clean_text)
                blocks.append({
                    "x0": x0,
                    "y0": y0,
                    "x1": x1,
                    "y1": y1,
                    "text": clean_text,
                    "page": page_idx + 1
                })
                
    # If we extracted significant text (e.g. >100 characters per page average), return it
    if direct_extracted_char_count > (100 * len(doc)):
        logger.info(f"Using direct PDF text extraction. Character count: {direct_extracted_char_count}")
        return blocks, False

    # 2. OCR Fallback: Render pages to images and run PaddleOCR
    logger.info("Direct text extraction found very little text. Falling back to OCR...")
    ocr = get_paddle_ocr()
    if ocr is None:
        # If OCR fails to load on this environment, return whatever direct text we found
        logger.warning("OCR engine unavailable. Returning direct text blocks.")
        return blocks, False

    ocr_blocks = []
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        # Render page to PNG bytes
        pix = page.get_pixmap(dpi=150)
        img_data = pix.tobytes("png")
        
        # Run OCR
        try:
            # PaddleOCR takes file path or numpy array. We can pass image bytes to a temp file or use PIL
            img = Image.open(io.BytesIO(img_data))
            # Temporary file write (PaddleOCR is happiest with file paths)
            temp_filename = f"temp_page_{page_idx}.png"
            img.save(temp_filename)
            
            result = ocr.ocr(temp_filename, cls=True)
            
            # Clean up temp file
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
                
            if result and result[0]:
                for line in result[0]:
                    box = line[0]  # List of 4 points: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
                    text_str, confidence = line[1]
                    
                    # Calculate bounding box coordinates
                    xs = [pt[0] for pt in box]
                    ys = [pt[1] for pt in box]
                    x0, x1 = min(xs), max(xs)
                    y0, y1 = min(ys), max(ys)
                    
                    ocr_blocks.append({
                        "x0": float(x0),
                        "y0": float(y0),
                        "x1": float(x1),
                        "y1": float(y1),
                        "text": text_str.strip(),
                        "page": page_idx + 1
                    })
        except Exception as ocr_err:
            logger.error(f"Error running OCR on page {page_idx + 1}: {ocr_err}")
            
    logger.info(f"OCR extraction completed. Found {len(ocr_blocks)} text blocks.")
    # Fallback to direct blocks if OCR returned nothing at all
    if not ocr_blocks:
        return blocks, False
        
    return ocr_blocks, True
