import os

# Bypass model source connectivity checks for offline/air-gapped environments
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import fitz  # PyMuPDF
import logging
from PIL import Image
import io

logger = logging.getLogger("robo-ocr-service")

# Global PaddleOCR instance placeholder
_paddle_ocr_instance = None

import numpy as np

def get_paddle_ocr():
    """
    Get or initialize the PaddleOCR instance dynamically, with error tolerance.
    """
    global _paddle_ocr_instance
    if _paddle_ocr_instance is not None:
        return _paddle_ocr_instance

    try:
        from paddleocr import PaddleOCR
        # Initialize PaddleOCR with optimized parameters for faster local CPU execution
        logger.info("Initializing PaddleOCR engine...")
        _paddle_ocr_instance = PaddleOCR(
            lang='en',
            ocr_version='PP-OCRv5',
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=True
        )
        # Warmup prediction on a small blank image to build C++ execution graph
        try:
            dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
            _paddle_ocr_instance.ocr(dummy_img)
        except Exception:
            pass
        logger.info("PaddleOCR successfully initialized and pre-warmed.")
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
        - blocks: list of dicts, each with {x0, y0, x1, y1, text, page} in standard 72 DPI points
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
                    "x0": float(x0),
                    "y0": float(y0),
                    "x1": float(x1),
                    "y1": float(y1),
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
        logger.warning("OCR engine unavailable. Returning direct text blocks.")
        return blocks, False

    ocr_blocks = []
    # 120 DPI provides optimal speed (<10s per page) while retaining high OCR precision
    target_dpi = 120
    scale = 72.0 / float(target_dpi)
    # Tax form data is always located on Page 1. Page 2+ are instruction pages.
    # Restricting OCR to Page 1 ensures processing under 12 seconds and prevents Page 2 text contamination.
    max_ocr_pages = 1
    
    for page_idx in range(max_ocr_pages):
        page = doc[page_idx]
        pix = page.get_pixmap(dpi=target_dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        img_np = np.array(img)
        
        # Run OCR in memory
        try:
            result = ocr.ocr(img_np)
            page_blocks_found = 0
            
            if result and result[0]:
                res_obj = result[0]
                if isinstance(res_obj, dict) and "rec_texts" in res_obj and "rec_boxes" in res_obj:
                    texts = res_obj["rec_texts"]
                    boxes = res_obj["rec_boxes"]
                    for idx, text_str in enumerate(texts):
                        box = boxes[idx]
                        x0, y0, x1, y1 = box[0] * scale, box[1] * scale, box[2] * scale, box[3] * scale
                        ocr_blocks.append({
                            "x0": float(x0),
                            "y0": float(y0),
                            "x1": float(x1),
                            "y1": float(y1),
                            "text": text_str.strip(),
                            "page": page_idx + 1
                        })
                        page_blocks_found += 1
                else:
                    for line in res_obj:
                        box = line[0]  # [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
                        text_str, confidence = line[1]
                        xs = [pt[0] * scale for pt in box]
                        ys = [pt[1] * scale for pt in box]
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
                        page_blocks_found += 1

            # Early exit: tax forms have all core data on Page 1. 
            # If Page 1 returned sufficient text blocks (>8), avoid unnecessary OCR on instruction pages.
            if page_idx == 0 and page_blocks_found >= 8:
                break

        except Exception as ocr_err:
            logger.error(f"Error running OCR on page {page_idx + 1}: {ocr_err}")
            
    logger.info(f"OCR extraction completed. Found {len(ocr_blocks)} text blocks.")
    if not ocr_blocks:
        return blocks, False
        
    return ocr_blocks, True
