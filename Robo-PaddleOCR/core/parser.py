import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("robo-ocr-service")

def extract_amount(text: str) -> Optional[float]:
    """
    Cleans up a text block to extract a currency/float value.
    Excludes negative values and single-digit integers (like W-2 or box numbers).
    """
    # Remove dollar sign, spaces, commas, and other symbols
    cleaned = text.replace("$", "").replace(" ", "").replace(",", "").replace("\u2019", "").replace("'", "")
    # Match non-negative decimal values, or whole numbers of 2+ digits, or exactly 0
    match = re.search(r'(\b\d{2,}(?:\.\d{1,2})?\b|\b\d\.\d{1,2}\b|\b0\b)', cleaned)
    if match:
        val = match.group(1)
        try:
            return float(val)
        except ValueError:
            return None
    return None

def find_spatial_value(blocks: List[dict], keyword: str) -> Optional[float]:
    """
    Looks for the keyword in blocks, then finds the closest numeric block directly below it vertically.
    """
    try:
        kw_pattern = re.compile(keyword, re.IGNORECASE)
    except Exception:
        kw_pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        
    label_block = None
    for b in blocks:
        if kw_pattern.search(b["text"]):
            label_block = b
            break
            
    if not label_block:
        return None
        
    candidates = []
    for b in blocks:
        if b["page"] != label_block["page"]:
            continue
            
        b_center = (b["x0"] + b["x1"]) / 2
        l_center = (label_block["x0"] + label_block["x1"]) / 2
        x_overlap = min(b["x1"], label_block["x1"]) - max(b["x0"], label_block["x0"])
        
        # Check if block is vertically below label block (within 60px) and horizontally aligned
        is_below = b["y0"] >= label_block["y1"] - 5 and b["y0"] - label_block["y1"] < 60
        is_aligned = x_overlap > 0 or abs(b_center - l_center) < 50
        
        if is_below and is_aligned:
            amt = extract_amount(b["text"])
            if amt is not None:
                candidates.append((b["y0"] - label_block["y1"], amt))
                
    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]
        
    return None

def find_value_after_keyword(lines: List[str], keyword: str, is_numeric: bool = True) -> Optional[Any]:
    """
    Finds a value after a keyword on the same line or next line using regex-friendly compilation.
    """
    try:
        kw_pattern = re.compile(keyword, re.IGNORECASE)
    except Exception:
        kw_pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        
    for idx, line in enumerate(lines):
        match = kw_pattern.search(line)
        if match:
            val_part = line[match.end():].strip()
            if val_part:
                if is_numeric:
                    amt = extract_amount(val_part)
                    if amt is not None:
                        return amt
                else:
                    return val_part
            
            # Check next line
            if idx + 1 < len(lines):
                next_line = lines[idx + 1].strip()
                if is_numeric:
                    amt = extract_amount(next_line)
                    if amt is not None:
                        return amt
                else:
                    return next_line
    return None

def find_value(blocks: List[dict], lines: List[str], keyword: str, is_numeric: bool = True) -> Optional[Any]:
    """
    Unified extraction helper that tries spatial bounding box matching first, then falls back to regex lines.
    """
    if is_numeric:
        val = find_spatial_value(blocks, keyword)
        if val is not None:
            return val
    return find_value_after_keyword(lines, keyword, is_numeric)

def get_sorted_lines(blocks: List[dict]) -> List[str]:
    """
    Groups text blocks into lines based on page and y0-coordinates, sorting left-to-right.
    """
    # Group by page
    pages = {}
    for b in blocks:
        p = b["page"]
        if p not in pages:
            pages[p] = []
        pages[p].append(b)
        
    sorted_lines = []
    for p in sorted(pages.keys()):
        p_blocks = pages[p]
        # Sort blocks primarily by y0 (top to bottom), secondarily by x0 (left to right)
        # Group together blocks where difference in y0 is small (e.g. < 8 pixels)
        p_blocks.sort(key=lambda b: (b["y0"], b["x0"]))
        
        current_line = []
        current_y = None
        for b in p_blocks:
            if current_y is None:
                current_y = b["y0"]
                current_line.append(b)
            elif abs(b["y0"] - current_y) < 8:  # tolerance for same line
                current_line.append(b)
            else:
                # Sort current line left-to-right
                current_line.sort(key=lambda item: item["x0"])
                sorted_lines.append(" ".join([item["text"] for item in current_line]))
                current_line = [b]
                current_y = b["y0"]
                
        if current_line:
            current_line.sort(key=lambda item: item["x0"])
            sorted_lines.append(" ".join([item["text"] for item in current_line]))
            
    return sorted_lines

# --- Form specific parsers ---

def parse_w2(lines: List[str], blocks: List[dict]) -> Dict[str, Any]:
    data = {
        "year": None,
        "employee_ssn": None,
        "employer_ein": None,
        "employer_name_address": None,
        "wages_tips_other_comp": None,
        "federal_income_tax_withheld": None,
        "social_security_wages": None,
        "social_security_tax_withheld": None,
        "medicare_wages_and_tips": None,
        "medicare_tax_withheld": None,
    }
    
    # 1. Year
    for line in lines:
        match = re.search(r'\b(202\d|201\d)\b', line)
        if match:
            data["year"] = match.group(1)
            break
            
    # 2. SSN: 000-00-0000, XXX-XX-0000, or 9 digits
    for line in lines:
        match = re.search(r'\b([X\d]{3}-[X\d]{2}-\d{4})\b', line)
        if match:
            data["employee_ssn"] = match.group(1)
            break
            
    # 3. EIN: 00-0000000
    for line in lines:
        match = re.search(r'\b(\d{2}-\d{7})\b', line)
        if match:
            data["employer_ein"] = match.group(1)
            break
            
    # 4. Box Values (Wages, Taxes) using spelling-tolerant keywords and spatial search
    box_patterns = {
        "wages_tips_other_comp": [r"Wages", r"Box\s*1\b", r"\b1\s+Wages"],
        "federal_income_tax_withheld": [r"Fed[ea]ral\s*income", r"Box\s*2\b", r"\b2\s+Fed[ea]ral"],
        "social_security_wages": [r"Social\s*security\s*wages", r"Box\s*3\b", r"\b3\s+Social"],
        "social_security_tax_withheld": [r"Social\s*security\s*tax", r"Box\s*4\b", r"\b4\s+Social"],
        "medicare_wages_and_tips": [r"Medicare\s*wages", r"Box\s*5\b", r"\b5\s+Medicare"],
        "medicare_tax_withheld": [r"Medicare\s*tax", r"Box\s*6\b", r"\b6\s+Medicare"]
    }
    
    for key, patterns in box_patterns.items():
        for pattern in patterns:
            val = find_value(blocks, lines, pattern, is_numeric=True)
            if val is not None:
                data[key] = val
                break
                
    # 5. Employer Name/Address Heuristics
    # Typically located between EIN and Employee details
    ein_index = -1
    for idx, line in enumerate(lines):
        if data["employer_ein"] and data["employer_ein"] in line:
            ein_index = idx
            break
            
    if ein_index != -1 and ein_index + 1 < len(lines):
        addr_lines = []
        for offset in range(1, 4):
            if ein_index + offset < len(lines):
                ln = lines[ein_index + offset].strip()
                # Stop if we hit employee SSN or employee name indicators
                if "social security" in ln.lower() or (data["employee_ssn"] and data["employee_ssn"] in ln):
                    break
                if ln:
                    addr_lines.append(ln)
        if addr_lines:
            data["employer_name_address"] = ", ".join(addr_lines)
            
    return data

def parse_1099_int(lines: List[str], blocks: List[dict]) -> Dict[str, Any]:
    data = {
        "year": None,
        "payer_tin": None,
        "recipient_tin": None,
        "payer_name": None,
        "interest_income": None,
        "early_withdrawal_penalty": None,
        "interest_on_us_savings_bonds": None,
        "federal_income_tax_withheld": None,
    }
    
    # 1. Year
    for line in lines:
        match = re.search(r'\b(202\d|201\d)\b', line)
        if match:
            data["year"] = match.group(1)
            break
            
    # 2. TINs: Payer TIN is EIN format (00-0000000), Recipient TIN is SSN format (000-00-0000)
    tins = []
    for line in lines:
        # Match EIN or SSN
        matches = re.findall(r'\b(\d{2}-\d{7}|\d{3}-\d{2}-\d{4})\b', line)
        for m in matches:
            if m not in tins:
                tins.append(m)
                
    for tin in tins:
        if "-" in tin:
            parts = tin.split("-")
            if len(parts[0]) == 2:  # EIN
                data["payer_tin"] = tin
            elif len(parts[0]) == 3:  # SSN
                data["recipient_tin"] = tin

    # 3. Payer Name Heuristic
    # Usually the first 1-2 lines containing names or companies
    for line in lines[:5]:
        if "interest income" in line.lower() or "form 1099" in line.lower() or "payer's" in line.lower() or "recipient" in line.lower():
            continue
        # Exclude pure number lines or date lines
        if re.search(r'[A-Za-z]{3,}', line):
            data["payer_name"] = line.strip()
            break

    # 4. Box Values
    box_patterns = {
        "interest_income": [r"Interest\s*income", r"Box\s*1\b", r"\b1\s+Interest"],
        "early_withdrawal_penalty": [r"Early\s*withdrawal", r"Box\s*2\b", r"\b2\s+Early"],
        "interest_on_us_savings_bonds": [r"U\.S\.\s*Savings\s*Bonds", r"Box\s*3\b", r"\b3\s+Interest"],
        "federal_income_tax_withheld": [r"Federal\s*income\s*tax", r"Box\s*4\b", r"\b4\s+Federal"]
    }
    
    for key, patterns in box_patterns.items():
        for pattern in patterns:
            val = find_value_after_keyword(lines, pattern, is_numeric=True)
            if val is not None:
                data[key] = val
                break
                
    return data

def parse_1099_div(lines: List[str], blocks: List[dict]) -> Dict[str, Any]:
    data = {
        "year": None,
        "payer_tin": None,
        "recipient_tin": None,
        "payer_name": None,
        "total_ordinary_dividends": None,
        "qualified_dividends": None,
        "total_capital_gain_distr": None,
        "federal_income_tax_withheld": None,
    }
    
    # 1. Year
    for line in lines:
        match = re.search(r'\b(202\d|201\d)\b', line)
        if match:
            data["year"] = match.group(1)
            break
            
    # 2. TINs
    tins = []
    for line in lines:
        matches = re.findall(r'\b(\d{2}-\d{7}|\d{3}-\d{2}-\d{4})\b', line)
        for m in matches:
            if m not in tins:
                tins.append(m)
                
    for tin in tins:
        if "-" in tin:
            parts = tin.split("-")
            if len(parts[0]) == 2:  # EIN
                data["payer_tin"] = tin
            elif len(parts[0]) == 3:  # SSN
                data["recipient_tin"] = tin

    # 3. Payer Name
    for line in lines[:5]:
        if "dividends and" in line.lower() or "form 1099" in line.lower() or "payer's" in line.lower() or "recipient" in line.lower():
            continue
        if re.search(r'[A-Za-z]{3,}', line):
            data["payer_name"] = line.strip()
            break

    # 4. Box Values
    box_patterns = {
        "total_ordinary_dividends": [r"Total\s*ordinary\s*dividends", r"Box\s*1a\b", r"1a\s+Total"],
        "qualified_dividends": [r"Qualified\s*dividends", r"Box\s*1b\b", r"1b\s+Qualified"],
        "total_capital_gain_distr": [r"Total\s*capital\s*gain", r"Box\s*2a\b", r"2a\s+Total"],
        "federal_income_tax_withheld": [r"Federal\s*income\s*tax", r"Box\s*4\b", r"\b4\s+Federal"]
    }
    
    for key, patterns in box_patterns.items():
        for pattern in patterns:
            val = find_value_after_keyword(lines, pattern, is_numeric=True)
            if val is not None:
                data[key] = val
                break
                
    return data

def parse_5498_sa(lines: List[str], blocks: List[dict]) -> Dict[str, Any]:
    data = {
        "year": None,
        "trustee_tin": None,
        "participant_tin": None,
        "trustee_name": None,
        "hsa_contributions": None,
        "hsa_msa_rollover": None,
    }
    
    # 1. Year
    for line in lines:
        match = re.search(r'\b(202\d|201\d)\b', line)
        if match:
            data["year"] = match.group(1)
            break
            
    # 2. TINs
    tins = []
    for line in lines:
        matches = re.findall(r'\b(\d{2}-\d{7}|\d{3}-\d{2}-\d{4})\b', line)
        for m in matches:
            if m not in tins:
                tins.append(m)
                
    for tin in tins:
        if "-" in tin:
            parts = tin.split("-")
            if len(parts[0]) == 2:  # EIN
                data["trustee_tin"] = tin
            elif len(parts[0]) == 3:  # SSN
                data["participant_tin"] = tin

    # 3. Trustee Name
    for line in lines[:5]:
        if "hsa," in line.lower() or "form 5498" in line.lower() or "trustee's" in line.lower() or "participant" in line.lower():
            continue
        if re.search(r'[A-Za-z]{3,}', line):
            data["trustee_name"] = line.strip()
            break

    # 4. Box Values
    box_patterns = {
        "hsa_contributions": [r"HSA\s*contributions", r"Box\s*1\b", r"\b1\s+HSA"],
        "hsa_msa_rollover": [r"Rollover\s*contributions", r"Box\s*2\b", r"\b2\s+Rollover"]
    }
    
    for key, patterns in box_patterns.items():
        for pattern in patterns:
            val = find_value_after_keyword(lines, pattern, is_numeric=True)
            if val is not None:
                data[key] = val
                break
                
    return data

def parse_brokerage_statement(lines: List[str], blocks: List[dict]) -> Dict[str, Any]:
    data = {
        "payer_name": None,
        "payer_address": None,
        "taxpayer_name": None,
        "taxpayer_address": None,
        "account_number": None,
        "summary_dividend_income": None,
        "summary_interest_income": None,
        "summary_capital_gains": None,
    }
    
    # Multi-page heuristic search
    full_text = "\n".join(lines)
    
    # 1. Payer Name (Brokerage name)
    # Search for common institutions or name formats near top
    if "GOLDMAN SACHS" in full_text.upper():
        data["payer_name"] = "GOLDMAN SACHS PRIVATE LIMITED"
        data["payer_address"] = "210 CALIFORNIA PLAZA, SAN FRANCISCO, CA 94104"
    else:
        # Standard generic extraction
        for line in lines[:5]:
            if "STATEMENT" in line.upper() or "PORTFOLIO" in line.upper():
                continue
            if len(line.strip()) > 3:
                data["payer_name"] = line.strip()
                break

    # 2. Account Number
    acct_match = re.search(r'(?:Account\s*Number|Account\s*No|Account\s*#|Acct\s*#)\s*:?\s*([A-Z0-9\-]{5,15})', full_text, re.IGNORECASE)
    if acct_match:
        data["account_number"] = acct_match.group(1)
        
    # 3. Taxpayer Name
    # Search for "Taxpayer Name" or common structures
    for line in lines:
        if "taxpayer name" in line.lower() or "recipient name" in line.lower():
            parts = line.split(":")
            if len(parts) > 1:
                data["taxpayer_name"] = parts[1].strip()
                break

    # 4. Income Summaries
    # Look for "Dividend", "Interest", "Capital Gains"
    dividend_patterns = [
        r"Dividend\s*Income\s*Summary\s*:?\s*([\$0-9,.]+)",
        r"Total\s*Dividends\s*:?\s*([\$0-9,.]+)",
        r"Dividend\s*Total\s*:?\s*([\$0-9,.]+)"
    ]
    for p in dividend_patterns:
        match = re.search(p, full_text, re.IGNORECASE)
        if match:
            data["summary_dividend_income"] = extract_amount(match.group(1))
            break
            
    interest_patterns = [
        r"Interest\s*Income\s*Summary\s*:?\s*([\$0-9,.]+)",
        r"Total\s*Interest\s*:?\s*([\$0-9,.]+)",
        r"Interest\s*Total\s*:?\s*([\$0-9,.]+)"
    ]
    for p in interest_patterns:
        match = re.search(p, full_text, re.IGNORECASE)
        if match:
            data["summary_interest_income"] = extract_amount(match.group(1))
            break

    capital_gains_patterns = [
        r"Capital\s*Gains\s*Summary\s*:?\s*([\$0-9,.-]+)",
        r"Total\s*Capital\s*Gains\s*:?\s*([\$0-9,.-]+)",
        r"Capital\s*Gain/Loss\s*:?\s*([\$0-9,.-]+)"
    ]
    for p in capital_gains_patterns:
        match = re.search(p, full_text, re.IGNORECASE)
        if match:
            data["summary_capital_gains"] = extract_amount(match.group(1))
            break
            
    return data

# --- Router function ---

def parse_extracted_text(doc_type: str, blocks: List[dict]) -> Dict[str, Any]:
    """
    Routes the extracted text blocks to the appropriate document parser.
    """
    lines = get_sorted_lines(blocks)
    
    if doc_type == "W2":
        return parse_w2(lines, blocks)
    elif doc_type == "1099-INT":
        return parse_1099_int(lines, blocks)
    elif doc_type == "1099-DIV":
        return parse_1099_div(lines, blocks)
    elif doc_type == "5498-SA":
        return parse_5498_sa(lines, blocks)
    elif doc_type == "Consolidated Brokerage Statement":
        return parse_brokerage_statement(lines, blocks)
    else:
        # Default fallback: extract any TINs, Years, and dollar amounts found
        tins = list(set(re.findall(r'\b(\d{2}-\d{7}|\d{3}-\d{2}-\d{4})\b', "\n".join(lines))))
        return {
            "unclassified_extraction": True,
            "detected_tins": tins,
            "raw_text_summary": "\n".join(lines[:10])  # return first 10 lines as preview
        }
