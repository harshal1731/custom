"""Apply human-review fixes to training/ground_truth.json for needs_review files."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GT_PATH = ROOT / "training" / "ground_truth.json"
REVIEW_PATH = ROOT / "training" / "needs_review.json"


def _empty_5498() -> dict:
    """Field keys must match app/ocr/extractors/form_5498_sa.py."""
    return {
        "Year": None,
        "TRUSTEE'S or ISSUER'S name, street address, city, state, ZIP": None,
        "TRUSTEE'S or ISSUER'S TIN": None,
        "PARTICIPANT'S TIN": None,
        "PARTICIPANT'S name": None,
        "Street address (including apt. no.)": None,
        "City, state, and ZIP": None,
        "Account number": None,
        "1 Employee or self-employed person's Archer MSA contributions made": None,
        "2 Total contributions": None,
        "3 Total HSA or Archer MSA contributions made in following year": None,
        "4 Rollover contributions": None,
        "5 FMV of HSA, Archer MSA, or MA MSA": None,
        "6 HSA": None,
        "6 Archer MSA": None,
        "6 MA MSA": None,
    }


def main() -> int:
    gt = json.loads(GT_PATH.read_text(encoding="utf-8"))

    # --- W-2 #05: drop garbage box12/suffix / duplicated column noise ---
    w2_05 = gt["05 - Document - Form W-2.pdf"]["fields"]
    for k in (
        "Suff.",
        "12a Code/Amount",
        "12b Code/Amount",
        "12c Code/Amount",
        "12d Code/Amount",
        "13 Retirement plan",
        "13 Third-party sick pay",
        "14 Other",
        "15 State / Employer's state ID number",
    ):
        w2_05[k] = None
    if w2_05.get("2 Federal income tax withheld") == w2_05.get("1 Wages, tips, other compensation"):
        w2_05["2 Federal income tax withheld"] = None
    if w2_05.get("6 Medicare tax withheld") == w2_05.get("5 Medicare wages and tips"):
        w2_05["6 Medicare tax withheld"] = None
    wages = w2_05.get("1 Wages, tips, other compensation")
    medicare = w2_05.get("5 Medicare wages and tips")
    for k in (
        "8 Allocated tips",
        "10 Dependent care benefits",
        "16 State wages, tips, etc.",
        "17 State income tax",
        "18 Local wages, tips, etc.",
        "19 Local income tax",
    ):
        if w2_05.get(k) in {wages, medicare}:
            w2_05[k] = None

    # --- 1099-INT #06 ---
    int6 = gt["06 - Document - 1099 - INT.pdf"]["fields"]
    int6["Recipient's Name"] = "MARY F DICK"
    int6["Year"] = "2024"
    int6["14 Tax-exempt and tax credit bond CUSIP no."] = None
    int6["15 State"] = None
    int6["16 State identification no."] = None
    int6["FATCA filing Requirement"] = None
    int6["Payer's RTN (Optional)"] = None
    foreign = str(int6.get("7 Foreign country or U.S. possession") or "")
    if "negligence" in foreign.lower() or "denmark" in foreign.lower():
        int6["7 Foreign country or U.S. possession"] = None

    # --- 1099-DIV #06: blank IRS copy; keep only trusted IDs ---
    div6 = gt["06 - Document - 1099 - DIV.pdf"]["fields"]
    for k in list(div6.keys()):
        if k in {"Year", "Payer's TIN", "Recipient's TIN"}:
            continue
        div6[k] = None
    div6["Year"] = "2024"
    div6["Payer's TIN"] = "43-1912740"
    div6["Recipient's TIN"] = "XXX-XX-1032"
    div6["Recipient's Name"] = None

    # --- Brokerage #01 ---
    b01 = gt["01 - Document - Consolidated Brokerage Statement.pdf"]["fields"]
    b01["Recipient's Name"] = None
    b01["Payer Name"] = "Charles Schwab"

    # --- Brokerage #04 ---
    b04 = gt["04 - Document - Consolidated Brokerage Statement.pdf"]["fields"]
    b04["Recipient's Name"] = "AVA BISHOP"
    b04["Recipient's Street Address (including apt. no.)"] = "1759 PIERCE ST"
    b04["Recipient City"] = "JERSEY CITY"
    b04["Recipient State"] = "NJ"
    b04["Recipient ZipCode"] = "07310"
    b04["Payer Name"] = "NATIONAL FINANCIAL SERVICES LLC"

    # --- Brokerage #05 Edward Jones (Progress Parkway is payer HQ, not recipient) ---
    b05 = gt["05 - Document - Consolidated Brokerage Statement.pdf"]["fields"]
    b05["Payer Name"] = "Edward Jones"
    b05["Payer Address"] = "201 Progress Parkway"
    b05["Payer City"] = "Maryland Heights"
    b05["Payer State"] = "MO"
    b05["Payer ZipCode"] = "63043-3042"
    b05["Recipient's Name"] = None
    b05["Recipient's Street Address (including apt. no.)"] = None
    b05["Recipient City"] = None
    b05["Recipient State"] = None
    b05["Recipient ZipCode"] = None
    b05["Account Number"] = None
    b05["Year"] = "2024"

    # --- Brokerage #07 ---
    b07 = gt["07 - Document - Consolidated Brokerage Statement.pdf"]["fields"]
    b07["Recipient City"] = "MT PLEASANT"
    b07["Account Number"] = None
    if b07.get("1a Total ordinary dividends") == b07.get("4 Federal income tax withheld"):
        b07["4 Federal income tax withheld"] = None
        b07["1a Total ordinary dividends"] = None

    # --- Brokerage #08 ---
    b08 = gt["08 - Document - Consolidated Brokerage Statement.pdf"]["fields"]
    b08["Recipient's Name"] = "The 2019 Chitwood Family Trust"
    b08["Recipient's Street Address (including apt. no.)"] = "126 Indigo Marsh Cir"
    b08["Recipient City"] = "Charleston"
    b08["Recipient State"] = "SC"
    b08["Recipient ZipCode"] = "29492-2700"
    b08["Payer City"] = "Saint Petersburg"
    b08["Payer State"] = "FL"
    b08["Payer ZipCode"] = "33716"
    b08["Payer Name"] = None
    b08["Payer Address"] = None
    b08["Account Number"] = None
    b08["Year"] = "2024"

    # --- Brokerage #09 Ameriprise ---
    b09 = gt["09 - Document - Consolidated Brokerage Statement.pdf"]["fields"]
    b09["Payer Name"] = "Ameriprise"
    b09["Recipient's Name"] = "ANAND S MEHTA"
    b09["Recipient's Street Address (including apt. no.)"] = "4058 BLACKMOOR ST"
    b09["Recipient City"] = "MOUNT PLEASANT"
    b09["Recipient State"] = "SC"
    b09["Recipient ZipCode"] = "29466-7160"
    b09["Account Number"] = None

    # --- Brokerage #10 JP Morgan (from text layer) ---
    b10 = gt["10 - Document - Consolidated Brokerage Statement.pdf"]["fields"]
    b10["Recipient's Name"] = "WREN LOUISE JANE FANNING"
    b10["Recipient's Street Address (including apt. no.)"] = "247 TUPELO LAKE DR"
    b10["Recipient City"] = "SUMMERVILLE"
    b10["Recipient State"] = "SC"
    b10["Recipient ZipCode"] = "29486-2464"
    b10["Payer Name"] = "J.P. MORGAN SECURITIES LLC"
    b10["Payer Address"] = "P.O. BOX 183211"
    b10["Payer City"] = "COLUMBUS"
    b10["Payer State"] = "OH"
    b10["Payer ZipCode"] = "43218"
    b10["Account Number"] = "994-56940"
    b10["Recipient TIN"] = "XXX-XX-6922"
    b10["Year"] = "2024"
    b10["Interest income"] = None
    if b10.get("4 Federal income tax withheld") == "1.24":
        # keep withholding; interest was duplicated
        pass

    # --- 5498-SA #02: HealthEquity scan (visual) ---
    sa02 = _empty_5498()
    sa02["Year"] = "2024"
    sa02["TRUSTEE'S or ISSUER'S name, street address, city, state, ZIP"] = (
        "HealthEquity Corporate, 15 West Scenic Pointe Drive Suite 400, Draper, UT 84020"
    )
    sa02["TRUSTEE'S or ISSUER'S TIN"] = "52-2383166"
    sa02["PARTICIPANT'S TIN"] = "XXX-XX-0858"
    sa02["PARTICIPANT'S name"] = "James R. Austin"
    sa02["Street address (including apt. no.)"] = "6920 Academy Ln"
    sa02["City, state, and ZIP"] = "Lockport, NY 14094"
    sa02["Account number"] = "1616408"
    sa02["1 Employee or self-employed person's Archer MSA contributions made"] = "0.00"
    sa02["2 Total contributions"] = "9300.00"  # printed; red-ink note is annotation only
    sa02["3 Total HSA or Archer MSA contributions made in following year"] = "0.00"
    sa02["4 Rollover contributions"] = "0.00"
    sa02["5 FMV of HSA, Archer MSA, or MA MSA"] = "36531.33"
    sa02["6 HSA"] = "Yes"
    gt["02 - Document - Form 5498 - SA.pdf"]["form_type"] = "5498-SA"
    gt["02 - Document - Form 5498 - SA.pdf"]["expected_form_type"] = "5498-SA"
    gt["02 - Document - Form 5498 - SA.pdf"]["fields"] = sa02
    gt["02 - Document - Form 5498 - SA.pdf"]["status"] = "reviewed"

    # --- 5498-SA #05: digital PDF — verified ---
    sa05 = _empty_5498()
    sa05["Year"] = "2024"
    sa05["TRUSTEE'S or ISSUER'S name, street address, city, state, ZIP"] = (
        "Central Trust Bank, 238 Madison St, Jefferson City, MO 65101"
    )
    sa05["TRUSTEE'S or ISSUER'S TIN"] = "43-0975002"
    sa05["PARTICIPANT'S name"] = "BRANWELL KAPELUCK"
    sa05["PARTICIPANT'S TIN"] = "248-43-0203"
    sa05["Street address (including apt. no.)"] = "34 BROUGHTON RD"
    sa05["City, state, and ZIP"] = "CHARLESTON, SC 29407-7548"
    sa05["Account number"] = "1000001772800"
    sa05["1 Employee or self-employed person's Archer MSA contributions made"] = "0.00"
    sa05["2 Total contributions"] = "1200.00"
    sa05["3 Total HSA or Archer MSA contributions made in following year"] = "0.00"
    sa05["4 Rollover contributions"] = "0.00"
    sa05["5 FMV of HSA, Archer MSA, or MA MSA"] = "52.75"
    sa05["6 HSA"] = "Yes"
    gt["05 - Document - Form 5498 - SA.pdf"]["form_type"] = "5498-SA"
    gt["05 - Document - Form 5498 - SA.pdf"]["expected_form_type"] = "5498-SA"
    gt["05 - Document - Form 5498 - SA.pdf"]["fields"] = sa05
    gt["05 - Document - Form 5498 - SA.pdf"]["status"] = "reviewed"

    # --- 5498-SA #07 / #09: identical REV FCU / Rhonda L Walden (visual) ---
    sa_rev = _empty_5498()
    sa_rev["Year"] = "2023"
    sa_rev["TRUSTEE'S or ISSUER'S name, street address, city, state, ZIP"] = (
        "REV FEDERAL CREDIT UNION, 200 MARYMEADE DR, SUMMERVILLE SC 29483, (843) 832-2600"
    )
    sa_rev["TRUSTEE'S or ISSUER'S TIN"] = "57-0377963"
    sa_rev["PARTICIPANT'S TIN"] = "XXX-XX-6651"
    sa_rev["PARTICIPANT'S name"] = "RHONDA L WALDEN"
    sa_rev["Street address (including apt. no.)"] = "536 JERICO DR"
    sa_rev["City, state, and ZIP"] = "RUTHERFORDTON, NC 28139"
    sa_rev["Account number"] = "02-01"
    sa_rev["1 Employee or self-employed person's Archer MSA contributions made"] = "0.00"
    sa_rev["2 Total contributions"] = "0.00"
    sa_rev["3 Total HSA or Archer MSA contributions made in following year"] = "0.00"
    sa_rev["4 Rollover contributions"] = "0.00"
    sa_rev["5 FMV of HSA, Archer MSA, or MA MSA"] = "3937.51"
    sa_rev["6 HSA"] = "Yes"
    for fname in (
        "07 - Document - Form 5498 - SA.pdf",
        "09 - Document - Form 5498 - SA.pdf",
    ):
        gt[fname]["form_type"] = "5498-SA"
        gt[fname]["expected_form_type"] = "5498-SA"
        gt[fname]["fields"] = dict(sa_rev)
        gt[fname]["status"] = "reviewed"

    for fname in (
        "05 - Document - Form W-2.pdf",
        "06 - Document - 1099 - INT.pdf",
        "06 - Document - 1099 - DIV.pdf",
        "01 - Document - Consolidated Brokerage Statement.pdf",
        "04 - Document - Consolidated Brokerage Statement.pdf",
        "05 - Document - Consolidated Brokerage Statement.pdf",
        "07 - Document - Consolidated Brokerage Statement.pdf",
        "08 - Document - Consolidated Brokerage Statement.pdf",
        "09 - Document - Consolidated Brokerage Statement.pdf",
        "10 - Document - Consolidated Brokerage Statement.pdf",
    ):
        gt[fname]["status"] = "reviewed"

    GT_PATH.write_text(json.dumps(gt, indent=2), encoding="utf-8")

    remaining = [
        {
            "file": fname,
            "note": "Partial — still needs visual confirmation",
            "form_type": payload.get("form_type"),
            "fields": {k: v for k, v in (payload.get("fields") or {}).items() if v is not None},
        }
        for fname, payload in gt.items()
        if payload.get("status") == "reviewed_partial"
    ]
    REVIEW_PATH.write_text(json.dumps(remaining, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {GT_PATH}")
    print(f"Remaining partial reviews: {len(remaining)}")
    for r in remaining:
        print(f"  - {r['file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
