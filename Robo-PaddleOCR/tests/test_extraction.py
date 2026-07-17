import os
import pytest
from core.classifier import classify_document
from core.parser import parse_extracted_text, extract_amount
from core.ocr_engine import extract_text_from_pdf

def test_classifier():
    assert classify_document("This is a Wage and Tax Statement Form W-2 for the year 2022.") == "W2"
    assert classify_document("FORM 1099-INT INTEREST INCOME STATEMENT") == "1099-INT"
    assert classify_document("Dividends and Distributions Form 1099-DIV") == "1099-DIV"
    assert classify_document("Form 5498-SA HSA Archer MSA Contributions") == "5498-SA"
    assert classify_document("CONSOLIDATED BROKERAGE STATEMENT Goldman Sachs") == "Consolidated Brokerage Statement"
    assert classify_document("Some unknown document with no tax forms info") == "Unknown"

def test_extract_amount_util():
    assert extract_amount("$1,234.56") == 1234.56
    assert extract_amount("1200") == 1200.0
    assert extract_amount(" Wages: 50,000.00 USD ") == 50000.00
    assert extract_amount("no numbers here") is None

def test_parser_routing_unknown():
    blocks = [{"x0": 0, "y0": 0, "x1": 100, "y1": 10, "text": "Random Text", "page": 1}]
    result = parse_extracted_text("Unknown", blocks)
    assert result["unclassified_extraction"] is True
    assert "Random Text" in result["raw_text_summary"]

# Find sample documents paths
sample_dir = r"d:\Harshal Projects\Robo-CustomModel-OCR\01 - ROBO1040 - All Documents\01 - ROBO - Sample PDF Document - 10 Set"

@pytest.mark.skipif(not os.path.exists(sample_dir), reason="Sample documents not found in workspace")
def test_sample_files_extraction():
    """
    Test extraction on one file from each of the 5 form categories.
    Verifies that the parser runs without exceptions and extracts key-value pairs.
    """
    samples = [
        ("01 - W2 Form - Sample Document (10 Set)", "01 - Document - Form W-2.pdf", "W2"),
        ("02 - 1099 INT - Sample Document (10 Set)", "01 - Document - 1099 - INT.pdf", "1099-INT"),
        ("03 - 1099 DIV - Sample Document (10 Set)", "01 - Document - 1099 - DIV.pdf", "1099-DIV"),
        ("04 - Consolidated Brokerage Statement - Sample Document (10 Set)", "01 - Document - Consolidated Brokerage Statement.pdf", "Consolidated Brokerage Statement"),
        ("05 - 5498 SA - Sample Document (10 Set)", "01 - Document - Form 5498 - SA.pdf", "5498-SA")
    ]
    
    from core.ocr_engine import get_paddle_ocr
    ocr_available = get_paddle_ocr() is not None
    
    for subdir, filename, expected_type in samples:
        file_path = os.path.join(sample_dir, subdir, filename)
        assert os.path.exists(file_path), f"Sample file {file_path} does not exist"
        
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()
            
        blocks, ocr_used = extract_text_from_pdf(pdf_bytes)
        
        # Skip checking if OCR is not available and direct text extraction yielded nothing
        if len(blocks) == 0 and not ocr_available:
            continue
            
        # Verify text was extracted
        assert len(blocks) > 0, f"No text blocks extracted from {filename}"
        
        full_text = "\n".join([b["text"] for b in blocks])
        classified_type = classify_document(full_text)
        
        # Verify classification
        assert classified_type == expected_type, f"Failed to classify {filename}: expected {expected_type}, got {classified_type}"
        
        # Verify parsing
        data = parse_extracted_text(classified_type, blocks)
        assert isinstance(data, dict), f"Parser did not return a dict for {filename}"
        
        # Check specific outputs
        if expected_type == "W2":
            # Form W-2 should extract basic items
            assert "employee_ssn" in data
            assert "employer_ein" in data
        elif expected_type == "1099-INT":
            assert "payer_tin" in data
            assert "recipient_tin" in data
        elif expected_type == "1099-DIV":
            assert "payer_tin" in data
            assert "recipient_tin" in data
        elif expected_type == "5498-SA":
            assert "trustee_tin" in data
            assert "participant_tin" in data
        elif expected_type == "Consolidated Brokerage Statement":
            assert "account_number" in data
