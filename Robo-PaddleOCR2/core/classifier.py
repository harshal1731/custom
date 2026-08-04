import re

def classify_document(full_text: str) -> str:
    """
    Classify the document type based on exact anchor text strings.
    Supports: W2, 1099-INT, 1099-DIV, 5498-SA, Consolidated Brokerage Statement.
    """
    text_upper = full_text.upper()

    # 1. Consolidated Brokerage Statement (Check first as it may contain sub-form text like 1099-INT/DIV)
    if "CONSOLIDATED BROKERAGE" in text_upper or "BROKERAGE STATEMENT" in text_upper or "CONSOLIDATED TAX REPORTING" in text_upper or "SCHWAB ONE" in text_upper or "GOLDMAN SACHS" in text_upper:
        return "Consolidated Brokerage Statement"

    # 2. Form 5498-SA
    if "5498-SA" in text_upper or "5498 - SA" in text_upper or "FORM 5498" in text_upper or "HSA, ARCHER MSA" in text_upper or "HSA CONTRIBUTIONS" in text_upper:
        return "5498-SA"

    # 3. Form 1099-DIV
    if "1099-DIV" in text_upper or "1099 - DIV" in text_upper or "DIVIDENDS AND DISTRIBUTIONS" in text_upper or "ORDINARY DIVIDENDS" in text_upper:
        return "1099-DIV"

    # 4. Form 1099-INT
    if "1099-INT" in text_upper or "1099 - INT" in text_upper or "INTEREST INCOME" in text_upper:
        return "1099-INT"

    # 5. Form W-2
    if "FORM W-2" in text_upper or "W-2" in text_upper or "WAGE AND TAX STATEMENT" in text_upper or "SOCIAL SECURITY WAGES" in text_upper:
        return "W2"

    # Fallbacks for general tax forms
    if "W2" in text_upper or "MEDICARE WAGES" in text_upper:
        return "W2"

    return "Unknown"
