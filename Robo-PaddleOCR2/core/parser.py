import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("robo-ocr-service")

# Hallucination prevention: maximum plausible tax form value (10 million)
_MAX_TAX_AMOUNT = 10_000_000.0

# Words that indicate a line is a form label / header — not a data value
_FORM_LABEL_WORDS = re.compile(
    r'\b(OMB|statement|department|treasury|form|copy|instructions|page|void|corrected|'
    r'recipient|payer|employee|employer|box|control|number|see|notice|for|the|and|or|'
    r'wages|tips|comp|medicare|security|federal|income|tax|withheld|zip|address|city|state)\b',
    re.IGNORECASE
)

# IRS form numbers and tax years to exclude from currency amount extraction
_FORM_NUMBERS_AND_YEARS = {1099.0, 1040.0, 5498.0, 1098.0, 1095.0, 2020.0, 2021.0, 2022.0, 2023.0, 2024.0, 2025.0, 2026.0}

def extract_amount(text: str) -> Optional[float]:
    """
    Cleans up a text block to extract a currency/float value.
    Excludes negative values, single-digit integers, form numbers (1099, 1040, etc.), tax years (2024), and unreasonably large numbers.
    """
    # Reject strings containing form headers or year titles (unless explicit $ symbol present)
    if re.search(r'\b(Form|Copy|OMB|Tax\s*Year|1099\s*-|5498\s*-|W-2)\b', text, re.IGNORECASE) and "$" not in text:
        return None

    cleaned = text.replace("$", "").replace(" ", "").replace(",", "").replace("\u2019", "").replace("'", "")
    match = re.search(r'(\b\d{1,}(?:\.\d{1,2})\b|\b\d{2,}\b|\b0\b)', cleaned)
    if match:
        val = match.group(1)
        try:
            result = float(val)
            if result in _FORM_NUMBERS_AND_YEARS:
                return None
            if result > _MAX_TAX_AMOUNT:
                return None
            return result
        except ValueError:
            return None
    return None

# Words that indicate a line is a table column header or form label — not an institution name
_HEADER_LABEL_WORDS = re.compile(
    r'\b(dividends|distributions|tax|withheld|possession|ordinary|qualified|capital|gain|'
    r'foreign|cash|liquidation|federal|income|amount|account|number|recipient|payer|'
    r'statement|instructions|copy|omb|form|department|treasury|paid|possessions)\b',
    re.IGNORECASE
)

def extract_payer_name(lines: List[str]) -> Optional[str]:
    """
    Extracts the official Payer/Trustee Name from tax form lines.
    Prioritizes text following 'Payer's Details' or 'PAYER'S name', excluding addresses and table headers.
    """
    payer_header_pattern = re.compile(r'(?:payer|trustee)\s*(?:\'?s)?\s*(?:details|name|address)', re.IGNORECASE)
    
    for idx, line in enumerate(lines):
        if payer_header_pattern.search(line):
            for offset in range(1, 6):
                if idx + offset < len(lines):
                    candidate = lines[idx + offset].strip()
                    clean_cand = re.sub(r'[\$\s0-9\.\,]+.*$', '', candidate).strip()
                    clean_cand = re.sub(r'\b\d+[a-z]?\s+Section.*$', '', clean_cand, flags=re.IGNORECASE).strip()
                    
                    if not clean_cand:
                        clean_cand = candidate.split("$")[0].strip()
                        
                    if re.match(r'^(po\s*box|p\.o\.\s*box|\d+\s+[a-z]+)', clean_cand, re.IGNORECASE):
                        continue
                        
                    if _is_name_line(clean_cand):
                        return clean_cand

    institution_keywords = re.compile(
        r'\b(computershare|bank|trust|schwab|fidelity|merrill|vanguard|wells|chase|citi|'
        r'goldman|morgan|edward|raymond|pershing|financial|securities|insurance|national)\b',
        re.IGNORECASE
    )
    for line in lines:
        clean_line = line.split("$")[0].strip()
        if institution_keywords.search(clean_line) and _is_name_line(clean_line):
            if not re.match(r'^(po\s*box|p\.o\.\s*box|\d+\s+[a-z]+)', clean_line, re.IGNORECASE):
                return clean_line

    for line in lines[:15]:
        clean_line = line.split("$")[0].strip()
        if _is_name_line(clean_line) and not _HEADER_LABEL_WORDS.search(clean_line):
            if not re.match(r'^(po\s*box|p\.o\.\s*box|\d+\s+[a-z]+)', clean_line, re.IGNORECASE):
                return clean_line
            
    return None

def _is_name_line(line: str) -> bool:
    """
    Returns True if a line looks like it contains a real institution/person name
    rather than a form label, header, or instruction text.
    """
    line = line.strip()
    if not line or len(line) < 3:
        return False
    # Must have at least 3 alpha chars
    if not re.search(r'[A-Za-z]{3,}', line):
        return False
    # Reject lines that are mostly form label keywords
    label_matches = len(_FORM_LABEL_WORDS.findall(line))
    word_count = len(line.split())
    if word_count > 0 and (label_matches / word_count) > 0.5:
        return False
    # Reject lines starting with common non-name patterns
    if re.match(r'^(\d|Page|Copy|OMB|Form|Box|Tax Year|Department|See|For)', line, re.IGNORECASE):
        return False
    # Reject lines containing email/URL patterns
    if re.search(r'@|www\.|http|\.com|\.gov', line, re.IGNORECASE):
        return False
    # Reject lines that are obviously addresses (have ZIP codes / state abbreviations mid-line with numbers)
    if re.search(r'\b[A-Z]{2}\s+\d{5}\b', line):
        return False
    return True

def find_spatial_value(blocks: List[dict], keyword: str) -> Optional[float]:
    """
    Looks for the keyword in blocks, then finds the closest numeric block 
    either directly to the right (same row) or directly below it vertically.
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
        
    l_cy = (label_block["y0"] + label_block["y1"]) / 2
    l_cx = (label_block["x0"] + label_block["x1"]) / 2

    candidates = []
    for b in blocks:
        if b["page"] != label_block["page"] or b == label_block:
            continue
            
        b_cy = (b["y0"] + b["y1"]) / 2
        b_cx = (b["x0"] + b["x1"]) / 2
        
        amt = extract_amount(b["text"])
        if amt is None:
            continue

        # 1. Check if block is to the RIGHT on the same horizontal row (within 8pt vertically)
        is_same_row = abs(b_cy - l_cy) < 8 and b["x0"] >= label_block["x0"] - 5
        
        # 2. Check if block is BELOW label block (within 75pt vertically) and horizontally aligned
        x_overlap = min(b["x1"], label_block["x1"]) - max(b["x0"], label_block["x0"])
        is_below = b["y0"] >= label_block["y1"] - 5 and (b["y0"] - label_block["y1"]) < 75
        is_aligned = x_overlap > -30 or abs(b_cx - l_cx) < 90

        if is_same_row:
            dist = abs(b["x0"] - label_block["x1"])
            candidates.append((dist, amt))
        elif is_below and is_aligned:
            # Vertical gap distance
            v_gap = b["y0"] - label_block["y1"]
            candidates.append((v_gap + 10, amt))
                
    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]
        
    return None

def find_value_after_keyword(lines: List[str], keyword: str, is_numeric: bool = True) -> Optional[Any]:
    """
    Finds a value after a keyword on the same line, next line, or 2 lines after.
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
            
            # Check next 2 lines
            for offset in (1, 2):
                if idx + offset < len(lines):
                    next_line = lines[idx + offset].strip()
                    if is_numeric:
                        amt = extract_amount(next_line)
                        if amt is not None:
                            return amt
                    else:
                        if next_line and _is_name_line(next_line):
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
    Groups text blocks into lines based on page and y0-coordinates (tolerance: 10 points).
    """
    pages = {}
    for b in blocks:
        p = b["page"]
        if p not in pages:
            pages[p] = []
        pages[p].append(b)
        
    sorted_lines = []
    for p in sorted(pages.keys()):
        p_blocks = pages[p]
        p_blocks.sort(key=lambda b: (b["y0"], b["x0"]))
        
        current_line = []
        current_y = None
        for b in p_blocks:
            if current_y is None:
                current_y = b["y0"]
                current_line.append(b)
            elif abs(b["y0"] - current_y) < 10:
                current_line.append(b)
            else:
                current_line.sort(key=lambda item: item["x0"])
                sorted_lines.append(" ".join([item["text"] for item in current_line]))
                current_line = [b]
                current_y = b["y0"]
                
        if current_line:
            current_line.sort(key=lambda item: item["x0"])
            sorted_lines.append(" ".join([item["text"] for item in current_line]))
            
    return sorted_lines

def extract_tins(lines: List[str]) -> Dict[str, Optional[str]]:
    """
    Extracts Payer/Trustee TIN (EIN format XX-XXXXXXX) and Recipient/Participant TIN 
    (SSN format XXX-XX-XXXX, masked XXX-XX-1234, trailing ****-3531, or unformatted 9-digit numbers).
    Excludes IRS OMB form numbers (1545-XXXX), Control Numbers, and Payer TIN duplicates.
    """
    payer_tin = None
    recipient_tin = None
    
    full_text = "\n".join(lines)
    
    # 1. Search for Payer/Trustee TIN (EIN format) first
    payer_kw_pattern = re.compile(
        r'(?:payer|trustee|employer)\s*(?:\'?s)?\s*(?:tin|ein|id|number|identification)?(?:\s*no\.?)?',
        re.IGNORECASE
    )
    for idx, line in enumerate(lines):
        match = payer_kw_pattern.search(line)
        if match:
            candidate_texts = [line[match.end():]] + lines[idx+1:idx+3]
            for text_chunk in candidate_texts:
                ein_match = re.search(r'(\b\d{2}\s*[\-\s]\s*\d{7}\b|\b\d{9}\b)', text_chunk)
                if ein_match:
                    raw_ein = ein_match.group(1).replace(" ", "")
                    if not raw_ein.startswith("1545"):
                        if len(raw_ein) == 9 and "-" not in raw_ein:
                            payer_tin = f"{raw_ein[:2]}-{raw_ein[2:]}"
                        else:
                            payer_tin = raw_ein
                        break
            if payer_tin:
                break

    if not payer_tin:
        ein_matches = re.findall(r'\b(\d{2}\s*-\s*\d{7})\b', full_text)
        for m in ein_matches:
            clean_m = m.replace(" ", "")
            if not clean_m.startswith("1545"):
                payer_tin = clean_m
                break

    # Helper to check if candidate is valid recipient_tin
    def is_valid_recipient(candidate: str) -> bool:
        if not candidate or len(candidate) < 8:
            return False
        if candidate.startswith("1545"):
            return False
        # Ignore phone numbers or ZIP+4 codes (e.g. 02940-3006)
        if re.match(r'^\d{5}-\d{4}$', candidate) or re.match(r'^\d{3}-\d{4}$', candidate):
            return False
        if payer_tin:
            clean_p = payer_tin.replace("-", "")
            clean_c = candidate.replace("-", "")
            if clean_c in clean_p or clean_p in clean_c:
                return False
        return True

    # 2. High-priority explicit SSN / TIN keywords
    specific_recipient_pattern = re.compile(
        r'(?:recipient|participant|employee)\s*(?:\'?s)?\s*(?:tin|ssn|id|identification)[\s\w\.]*?[\s:]*',
        re.IGNORECASE
    )
    
    # Strictly match 3-2-4 SSN formats, 2 to 4-star masked SSNs (***-7624, ****-3531), or 9 digits
    ssn_regex = r'(?:^|[\s:])([\*X]{2,4}-\d{4}\b|\b[X\*\d]{3}-[X\*\d]{2}-\d{4}\b|\b\d{9}\b)'

    for idx, line in enumerate(lines):
        match = specific_recipient_pattern.search(line)
        if match:
            candidate_texts = [line[match.end():]] + lines[idx+1:idx+3]
            for text_chunk in candidate_texts:
                if "control" in text_chunk.lower():
                    continue
                ssn_match = re.search(ssn_regex, text_chunk, re.IGNORECASE)
                if ssn_match:
                    raw_ssn = ssn_match.group(1).replace(" ", "")
                    if is_valid_recipient(raw_ssn):
                        recipient_tin = raw_ssn
                        break
            if recipient_tin:
                break

    # 3. Fallback scan for standard/masked SSN patterns
    if not recipient_tin:
        ssn_matches = re.findall(ssn_regex, full_text, re.IGNORECASE)
        for m in ssn_matches:
            clean_m = m.replace(" ", "")
            if is_valid_recipient(clean_m):
                recipient_tin = clean_m
                break

    return {"payer_tin": payer_tin, "recipient_tin": recipient_tin}

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
            
    # 2. TINs
    tins = extract_tins(lines)
    data["employee_ssn"] = tins["recipient_tin"]
    data["employer_ein"] = tins["payer_tin"]
            
    # 3. Box Values (Wages, Taxes) using spelling-tolerant keywords and spatial search
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
                
    # 4. Employer Name/Address Heuristics
    ein_index = -1
    for idx, line in enumerate(lines):
        if data["employer_ein"] and data["employer_ein"] in line:
            ein_index = idx
            break

    _w2_label_pattern = re.compile(
        r'\b(wages|tips|comp|medicare|security|federal|income|tax|withheld|control|'
        r'number|copy|void|corrected|department|treasury|omb|see|instructions|'
        r'allocated|dependent|nonqualified|statutory|retirement|third|sick)\b',
        re.IGNORECASE
    )

    if ein_index != -1 and ein_index + 1 < len(lines):
        addr_lines = []
        for offset in range(1, 5):
            if ein_index + offset < len(lines):
                ln = lines[ein_index + offset].strip()
                if "social security" in ln.lower() or (data["employee_ssn"] and data["employee_ssn"] in ln):
                    break
                if _w2_label_pattern.search(ln):
                    continue
                if ln and not re.match(r'^[\d\s\.\-,]+$', ln) and len(ln) > 2:
                    addr_lines.append(ln)
        if addr_lines:
            data["employer_name_address"] = "; ".join(addr_lines[:2])
            
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
            
    # 2. TINs
    tins = extract_tins(lines)
    data["payer_tin"] = tins["payer_tin"]
    data["recipient_tin"] = tins["recipient_tin"]

    # 3. Payer Name
    data["payer_name"] = extract_payer_name(lines)

    # 4. Box Values
    box_patterns = {
        "interest_income": [r"\b1\s+Interest\s*income", r"Interest\s*income", r"Box\s*1\b"],
        "early_withdrawal_penalty": [r"\b2\s+Early\s*withdrawal", r"Early\s*withdrawal", r"Box\s*2\b"],
        "interest_on_us_savings_bonds": [r"\b3\s+U\.S\.\s*Savings", r"U\.S\.\s*Savings\s*Bonds", r"Box\s*3\b"],
        "federal_income_tax_withheld": [r"\b4\s+Federal\s*income", r"Federal\s*income\s*tax", r"Box\s*4\b"]
    }
    
    for key, patterns in box_patterns.items():
        for pattern in patterns:
            val = find_value(blocks, lines, pattern, is_numeric=True)
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
    tins = extract_tins(lines)
    data["payer_tin"] = tins["payer_tin"]
    data["recipient_tin"] = tins["recipient_tin"]

    # 3. Payer Name
    data["payer_name"] = extract_payer_name(lines)

    # 4. Box Values
    box_patterns = {
        "total_ordinary_dividends": [r"1a\s+Total\s*ordinary", r"Total\s*ordinary\s*dividends", r"Box\s*1a\b"],
        "qualified_dividends": [r"1b\s+Qualified", r"Qualified\s*dividends", r"Box\s*1b\b"],
        "total_capital_gain_distr": [r"2a\s+Total\s*capital", r"Total\s*capital\s*gain", r"Box\s*2a\b"],
        "federal_income_tax_withheld": [r"\b4\s+Federal\s*income", r"Federal\s*income\s*tax", r"Box\s*4\b"]
    }
    
    for key, patterns in box_patterns.items():
        for pattern in patterns:
            val = find_value(blocks, lines, pattern, is_numeric=True)
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
    tins = extract_tins(lines)
    data["trustee_tin"] = tins["payer_tin"]
    data["participant_tin"] = tins["recipient_tin"]

    # 3. Trustee Name
    data["trustee_name"] = extract_payer_name(lines)

    # 4. Box Values
    box_patterns = {
        "hsa_contributions": [r"\b1\s+HSA", r"HSA\s*contributions", r"Box\s*1\b"],
        "hsa_msa_rollover": [r"\b2\s+Rollover", r"Rollover\s*contributions", r"Box\s*2\b"]
    }
    
    for key, patterns in box_patterns.items():
        for pattern in patterns:
            val = find_value(blocks, lines, pattern, is_numeric=True)
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
    
    # 1. Payer Name (Brokerage/institution name)
    # Use _is_name_line to find the first clean, plausible name line
    # Prefer lines containing known brokerage names
    brokerage_keywords = re.compile(
        r'\b(schwab|fidelity|merrill|wells\s*fargo|vanguard|td\s*ameritrade|'
        r'edward\s*jones|goldman|morgan\s*stanley|raymond\s*james|pershing|'
        r'raymond|charles|financial|investments?|securities|bank|trust|advisors?)\b',
        re.IGNORECASE
    )
    for line in lines[:15]:
        ln = line.strip()
        if brokerage_keywords.search(ln) and _is_name_line(ln):
            data["payer_name"] = ln
            break
    # Fallback: first clean name-like line
    if not data["payer_name"]:
        for line in lines[:10]:
            if _is_name_line(line):
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
