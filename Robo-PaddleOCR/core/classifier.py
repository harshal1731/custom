import re

def classify_document(full_text: str) -> str:
    """
    Classify the document type based on anchor text strings.
    """
    text_upper = full_text.upper()

    # Classification rules
    if "FORM W-2" in text_upper or "WAGE AND TAX STATEMENT" in text_upper:
        return "W2"
    elif "1099-INT" in text_upper or "INTEREST INCOME" in text_upper:
        return "1099-INT"
    elif "1099-DIV" in text_upper or "DIVIDENDS AND DISTRIBUTIONS" in text_upper:
        return "1099-DIV"
    elif "5498-SA" in text_upper or "HSA, ARCHER MSA" in text_upper or "5498 - SA" in text_upper:
        return "5498-SA"
    elif "CONSOLIDATED BROKERAGE STATEMENT" in text_upper or "GOLDMAN SACHS PRIVATE" in text_upper or "BROKERAGE STATEMENT" in text_upper:
        return "Consolidated Brokerage Statement"
    
    # Check for general 1099 or tax form elements
    if "W-2" in text_upper:
        return "W2"
    if "1099" in text_upper:
        if "INT" in text_upper:
            return "1099-INT"
        if "DIV" in text_upper:
            return "1099-DIV"
        if "B" in text_upper or "BARTER" in text_upper:
            return "Capital Gain_1099-B"
    
    return "Unknown"
