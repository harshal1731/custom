import os
import glob
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app

DATASET_DIR = r"D:\Harshal Projects\robo1040-ocr-api-standalone\01 - ROBO - Sample PDF Document - 10 Set\01 - W2 Form - Sample Document (10 Set)"
client = TestClient(app)
headers = {"X-API-Key": "robo1040"}

# Complete Ground Truth benchmark map for all 10 sample W-2 PDF documents
GROUND_TRUTH = {
    "01 - Document - Form W-2.pdf": {
        "Year": "2024",
        "Employee's social security number": "XXX-XX-2930",
        "Employer identification number (EIN)": "57-1110444",
        "Employer's name, address, and ZIP code": "I INS U InC, Charleston, SC 29407",
        "Control number": "20230218-3",
        "Employee's first name and initial": "Thomas",
        "Last name": "Masi",
        "Employee's address and ZIP code": "PO Box 31058, Thomas Masi, SC 29417",
        "1 Wages, tips, other compensation": "2800.00",
        "2 Federal income tax withheld": "1365.22",
        "3 Social security wages": "2800.00",
        "4 Social security tax withheld": "173.60",
        "5 Medicare wages and tips": "2800.00",
        "6 Medicare tax withheld": "40.60",
        "15 State / Employer's state ID number": "SC 25411574-6",
        "16 State wages, tips, etc.": "2800.00",
        "17 State income tax": "113.68"
    },
    "02 - Document - Form W-2.pdf": {
        "Year": "2024",
        "Employee's social security number": "XXX-XX-3014",
        "Employer identification number (EIN)": "23-1945930",
        "Employer's name, address, and ZIP code": "THE VANGUARD GROUP INC, 100 VANGUARD BLVD, MALVERN, PA 19355",
        "Control number": "0000008287 UEY 1376 CCNT 16475",
        "Employee's first name and initial": "TERENCE P",
        "Last name": "HOWARD",
        "Employee's address and ZIP code": "1478 KINLOCH LANE, MOUNT PLEASANT, SC 29464",
        "1 Wages, tips, other compensation": "794416.25",
        "2 Federal income tax withheld": "176498.10",
        "3 Social security wages": "168600.00",
        "4 Social security tax withheld": "10453.20",
        "5 Medicare wages and tips": "794416.25",
        "6 Medicare tax withheld": "16868.79",
        "12a Code/Amount": "W 8300.00",
        "12b Code/Amount": "AA 19723.00",
        "12c Code/Amount": "DD 25310.98",
        "13 Retirement plan": "Yes",
        "14 Other": "26.00 LST",
        "15 State / Employer's state ID number": "SC 25608545 3",
        "16 State wages, tips, etc.": "700842.64",
        "17 State income tax": "43108.61"
    },
    "03 - Document - Form W-2.pdf": {
        "Year": "2024",
        "Employee's social security number": "047-52-7330",
        "Employer identification number (EIN)": "86-2232853",
        "Employer's name, address, and ZIP code": "BAD BUNNIES COFFEE LLC, 242 ASHLEY AVE, CHARLESTON, SC 29402",
        "Employee's first name and initial": "Richard",
        "Last name": "Harden",
        "Employee's address and ZIP code": "242 Ashley Ave Apt B, Charleston, SC 29403",
        "1 Wages, tips, other compensation": "46000.00",
        "2 Federal income tax withheld": "8740.92",
        "3 Social security wages": "46000.00",
        "4 Social security tax withheld": "2852.00",
        "5 Medicare wages and tips": "46000.00",
        "6 Medicare tax withheld": "667.00",
        "15 State / Employer's state ID number": "SC 11173208-2",
        "16 State wages, tips, etc.": "46000.00",
        "17 State income tax": "2331.05"
    },
    "04 - Document - Form W-2.pdf": {
        "Year": "2024",
        "Employee's social security number": "XXX-XX-7190",
        "Employer identification number (EIN)": "57-0935917",
        "Employer's name, address, and ZIP code": "UMA Common Paymaster, 1 Poston Road, Charleston, SC 29407",
        "Employee's first name and initial": "John R",
        "Last name": "Freedy",
        "Employee's address and ZIP code": "872 Parrot Creek Way, CHARLESTON, SC 29412",
        "1 Wages, tips, other compensation": "161764.56",
        "2 Federal income tax withheld": "20465.79",
        "3 Social security wages": "145982.65",
        "4 Social security tax withheld": "9050.93",
        "5 Medicare wages and tips": "161764.56",
        "6 Medicare tax withheld": "2345.60",
        "7 Social security tips": "1584.00",
        "12a Code/Amount": "C 1584.00",
        "13 Retirement plan": "Yes",
        "15 State / Employer's state ID number": "SC 25285895-6",
        "16 State wages, tips, etc.": "161764.56",
        "17 State income tax": "7170.09"
    },
    "05 - Document - Form W-2.pdf": {
        "Year": "2024",
        "Employee's social security number": "242-93-5188",
        "Employer identification number (EIN)": "26-0795633",
        "Employer's name, address, and ZIP code": "CLEARBLADE, INC., STE 250, 1701 DIRECTORS BLVD, AUSTIN, TX 78744",
        "Employee's first name and initial": "JONATHAN M",
        "Last name": "WINGARD",
        "Employee's address and ZIP code": "303 BROADWAY STREET, AUSTIN, TX 78702",
        "1 Wages, tips, other compensation": "66795.30",
        "2 Federal income tax withheld": "6113.00",
        "3 Social security wages": "70395.30",
        "4 Social security tax withheld": "4364.51",
        "5 Medicare wages and tips": "70395.30",
        "6 Medicare tax withheld": "1020.73",
        "12a Code/Amount": "D 3600.00",
        "13 Retirement plan": "Yes",
        "16 State wages, tips, etc.": "66795.30",
        "17 State income tax": "6113.00"
    },
    "06 - Document - Form W-2.pdf": {
        "Year": "2024",
        "Employee's social security number": "XXX-XX-7606",
        "Employer identification number (EIN)": "57-1098556",
        "Employer's name, address, and ZIP code": "Medical University Hospital Authority, 1 Poston Road, Charleston, SC 29407",
        "Employee's first name and initial": "Margaret U",
        "Last name": "Gee",
        "Employee's address and ZIP code": "1429 BEDFORD DRIVE, CHARLESTON, SC 29407",
        "1 Wages, tips, other compensation": "104207.17",
        "2 Federal income tax withheld": "9568.85",
        "3 Social security wages": "114878.72",
        "4 Social security tax withheld": "7122.48",
        "5 Medicare wages and tips": "114878.72",
        "6 Medicare tax withheld": "1665.74",
        "12a Code/Amount": "C 722.40",
        "12b Code/Amount": "DD 18934.80",
        "13 Retirement plan": "Yes",
        "15 State / Employer's state ID number": "SC 254038928",
        "16 State wages, tips, etc.": "104207.17",
        "17 State income tax": "5238.08"
    },
    "07 - Document - Form W-2.pdf": {
        "Year": "2024",
        "Employee's social security number": "XXX-XX-4999",
        "Employer identification number (EIN)": "57-6000118",
        "Employer's name, address, and ZIP code": "BISHOP ENGLAND HIGH SCHOOL, 363 SEVEN FARMS DRIVE, CHARLESTON, SC 29492",
        "Control number": "140080 NCN2/1EU 000300",
        "Employee's first name and initial": "NETHA",
        "Last name": "KREAMER",
        "Employee's address and ZIP code": "501 RICE HOPE DRIVE, MT PLEASANT, SC 29464-0000",
        "1 Wages, tips, other compensation": "8500.00",
        "2 Federal income tax withheld": "1395.98",
        "3 Social security wages": "8500.00",
        "4 Social security tax withheld": "527.00",
        "5 Medicare wages and tips": "8500.00",
        "6 Medicare tax withheld": "123.25",
        "15 State / Employer's state ID number": "SC 250314618",
        "16 State wages, tips, etc.": "8500.00",
        "17 State income tax": "490.68"
    },
    "08 - Document - Form W-2.pdf": {
        "Year": "2024",
        "Employee's social security number": "247-47-0195",
        "Employer identification number (EIN)": "57-6001079",
        "Employer's name, address, and ZIP code": "Town of Mount Pleasant, 100 Ann Edwards Lane, Mount Pleasant, SC 29464 USA",
        "Control number": "000119540301",
        "Employee's first name and initial": "Thomas D",
        "Last name": "Plyler",
        "Employee's address and ZIP code": "3098 MOONLIGHT DRIVE, CHARLESTON, SC 29414 USA",
        "1 Wages, tips, other compensation": "66646.44",
        "2 Federal income tax withheld": "7264.49",
        "3 Social security wages": "77513.39",
        "4 Social security tax withheld": "4805.83",
        "5 Medicare wages and tips": "77513.39",
        "6 Medicare tax withheld": "1123.94",
        "12a Code/Amount": "D 1040.00",
        "12b Code/Amount": "G 2080.00",
        "12c Code/Amount": "AA 3640.00",
        "12d Code/Amount": "DD 30836.52",
        "13 Retirement plan": "Yes",
        "15 State / Employer's state ID number": "SC 250306048",
        "16 State wages, tips, etc.": "66646.44",
        "17 State income tax": "2814.62"
    },
    "09 - Document - Form W-2.pdf": {
        "Year": "2024",
        "Employee's social security number": "XXX-XX-0000",
        "Employer identification number (EIN)": "00-0000000"
    },
    "10 - Document - Form W-2.pdf": {
        "Year": "2024",
        "Employee's social security number": "259-11-0070",
        "Employer identification number (EIN)": "26-0402100",
        "Employer's name, address, and ZIP code": "Sente Mortgage, Inc., 4520 Burnet Rd, Austin, TX 78756-3025 USA",
        "Employee's first name and initial": "Michael D",
        "Last name": "Jewell",
        "Employee's address and ZIP code": "10 Piedmont Avenue, Charleston, SC 29403",
        "1 Wages, tips, other compensation": "30237.78",
        "2 Federal income tax withheld": "3495.88",
        "3 Social security wages": "34727.41",
        "4 Social security tax withheld": "2153.10",
        "5 Medicare wages and tips": "34727.41",
        "6 Medicare tax withheld": "503.55",
        "12a Code/Amount": "D 4489.63",
        "15 State / Employer's state ID number": "SC 11543942-7",
        "16 State wages, tips, etc.": "30237.78",
        "17 State income tax": "1432.93"
    }
}


def print_dataset_mismatch_report(fname: str, expected: dict, actual: dict) -> int:
    """Print ASCII mismatch table for a dataset PDF."""
    mismatches = 0
    print(f"\n=======================================================")
    print(f" REPORT FOR FILE: {fname}")
    print(f"=======================================================")
    print(f"{'Field Name':<40} | {'Expected Value':<35} | {'Actual Value':<35} | Status")
    print("-" * 118)

    for key, exp_val in expected.items():
        act_val = actual.get(key)
        exp_str = str(exp_val).strip() if exp_val is not None else ""
        act_str = str(act_val).strip() if act_val is not None else ""

        # Normalize string comparison
        status = "OK" if exp_str.lower() == act_str.lower() else "MISMATCH"
        if status != "OK":
            mismatches += 1

        print(f"{key:<40} | {exp_str[:35]:<35} | {act_str[:35]:<35} | {status}")

    total = len(expected)
    correct = total - mismatches
    acc = (correct / total) * 100 if total > 0 else 0
    print("-" * 118)
    print(f"File Total: {total} | Correct: {correct} | Mismatches: {mismatches} | Accuracy: {acc:.1f}%\n")
    return mismatches


@pytest.mark.parametrize("fname", sorted(GROUND_TRUTH.keys()))
def test_w2_dataset_e2e_extraction(fname: str):
    """End-to-End API test for each of the 10 W-2 dataset PDFs."""
    pdf_path = os.path.join(DATASET_DIR, fname)
    assert os.path.exists(pdf_path), f"File not found: {pdf_path}"

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    response = client.post("/api/v1/extract", headers=headers, files={"file": (fname, pdf_bytes, "application/pdf")})
    assert response.status_code == 200, f"API returned status code {response.status_code}: {response.text}"

    res = response.json()
    assert res["form_type"] == "W-2", f"Expected form_type 'W-2', got {res.get('form_type')}"

    fields = res.get("fields", {})
    expected = GROUND_TRUTH[fname]

    mismatches = print_dataset_mismatch_report(fname, expected, fields)
    assert mismatches == 0, f"{fname}: Found {mismatches} field mismatches out of {len(expected)} expected fields"
