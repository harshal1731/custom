import json
import fitz
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import get_settings

client = TestClient(app)
settings = get_settings()
headers = {"X-API-Key": settings.api_key}


def create_sample_w2_pdf(ssn="XXX-XX-7190", ein="57-0935917", emp_name="John R Freedy", box1="161764.56", box2="20465.79", box3="145982.65", box4="9050.93", box5="161764.56", box6="2345.60", box16="161764.56", box17="7170.09", st_id="SC 25285895-6"):
    """Helper to create synthetic multi-column 2-up W-2 digital PDFs."""
    doc = fitz.open()
    page = doc.new_page(width=1653, height=2139)
    
    # Left Copy B
    page.insert_text((50, 100), "a Employee's soc. sec. no. 1 Wages, tips, other comp. 2 Federal income tax withheld")
    page.insert_text((50, 140), f"{ssn} 1 Wages, tips, other comp. {box1} 2 Federal income tax withheld {box2}")
    page.insert_text((50, 200), "b Employer ID number (EIN) 3 Social security wages 4 Social security tax withheld")
    page.insert_text((50, 240), f"{ein} 3 Social security wages {box3} 4 Social security tax withheld {box4}")
    page.insert_text((50, 280), "5 Medicare wages and tips 6 Medicare tax withheld")
    page.insert_text((50, 310), f"5 Medicare wages and tips {box5} 6 Medicare tax withheld {box6}")
    page.insert_text((50, 350), "c Employer's name, address, and ZIP code")
    page.insert_text((50, 380), "UMA Common Paymaster, 1 Poston Road, Suite 350, Charleston, SC 29407")
    page.insert_text((50, 480), "e Employee's name, address, and ZIP code")
    page.insert_text((50, 520), f"{emp_name}")
    page.insert_text((50, 550), "872 Parrot Creek Way, CHARLESTON, SC 29412")
    page.insert_text((50, 600), "12a Code C 1584.00")
    page.insert_text((50, 640), "13 Retirement plan X")
    page.insert_text((50, 700), f"15 Employer's state ID number {st_id} 16 State wages, tips, etc. {box16} 17 State income tax {box17}")
    page.insert_text((50, 800), "Form W-2 Wage and Tax Statement 2024")

    # Right Copy 2
    page.insert_text((900, 100), "a Employee's soc. sec. no. 1 Wages, tips, other comp. 2 Federal income tax withheld")
    page.insert_text((900, 140), f"{ssn} 1 Wages, tips, other comp. {box1} 2 Federal income tax withheld {box2}")

    return doc.tobytes()



def print_mismatch_report(sample_name, expected, actual):
    """Generate a clean ASCII mismatch report table."""
    print(f"\n=======================================================")
    print(f" MISMATCH REPORT FOR SAMPLE: {sample_name}")
    print(f"=======================================================")
    print(f"{'Expected Field':<38} | {'Expected Value':<18} | {'Actual Value':<18} | {'Status'}")
    print("-" * 88)
    
    mismatches = 0
    for field, exp_val in expected.items():
        act_val = actual.get(field)
        status = "OK" if act_val == exp_val else "MISMATCH"
        if status == "MISMATCH":
            mismatches += 1
        print(f"{field:<38} | {str(exp_val):<18} | {str(act_val):<18} | {status}")
    print("-" * 88)
    print(f"Total Fields Checked: {len(expected)} | Total Mismatches: {mismatches}\n")
    return mismatches


def test_w2_e2e_api_full_sample():
    """Test full W-2 API extraction against ground truth."""
    pdf_bytes = create_sample_w2_pdf()
    files = {"file": ("test_w2.pdf", pdf_bytes, "application/pdf")}
    
    response = client.post("/api/v1/extract", headers=headers, files=files)
    assert response.status_code == 200
    res = response.json()
    assert res["form_type"] == "W-2"
    
    fields = res["fields"]
    
    expected = {
        "Year": "2024",
        "Employee's social security number": "XXX-XX-7190",
        "Employer identification number (EIN)": "57-0935917",
        "Employer's name, address, and ZIP code": "UMA Common Paymaster, 1 Poston Road, Suite 350, Charleston, SC 29407",
        "Employee's first name and initial": "John R",
        "Last name": "Freedy",
        "Employee's address and ZIP code": "872 Parrot Creek Way, CHARLESTON, SC 29412",
        "1 Wages, tips, other compensation": "161764.56",
        "2 Federal income tax withheld": "20465.79",
        "3 Social security wages": "145982.65",
        "4 Social security tax withheld": "9050.93",
        "12a Code/Amount": "C 1584.00",
        "13 Retirement plan": "Yes",
        "15 State / Employer's state ID number": "SC 25285895-6",
        "16 State wages, tips, etc.": "161764.56",
        "17 State income tax": "7170.09",
    }
    
    mismatches = print_mismatch_report("W-2 Standard 2-Up Sample", expected, fields)
    assert mismatches == 0, f"Found {mismatches} field mismatches in end-to-end W-2 API extraction"


def test_w2_e2e_api_alternate_employee():
    """Test second W-2 sample with alternate employee and employer data."""
    pdf_bytes = create_sample_w2_pdf(
        ssn="123-45-6789",
        ein="98-7654321",
        emp_name="Jane A Doe",
        box1="85000.00",
        box2="12500.00",
        box3="85000.00",
        box4="5270.00",
        box16="85000.00",
        box17="4200.00",
        st_id="NC 998877"
    )
    files = {"file": ("test_w2_alt.pdf", pdf_bytes, "application/pdf")}
    
    response = client.post("/api/v1/extract", headers=headers, files=files)
    assert response.status_code == 200
    res = response.json()
    fields = res["fields"]
    
    expected = {
        "Year": "2024",
        "Employee's social security number": "123-45-6789",
        "Employer identification number (EIN)": "98-7654321",
        "Employee's first name and initial": "Jane A",
        "Last name": "Doe",
        "1 Wages, tips, other compensation": "85000.00",
        "2 Federal income tax withheld": "12500.00",
        "3 Social security wages": "85000.00",
        "4 Social security tax withheld": "5270.00",
        "16 State wages, tips, etc.": "85000.00",
        "17 State income tax": "4200.00",
    }
    
    mismatches = print_mismatch_report("W-2 Alternate Employee Sample", expected, fields)
    assert mismatches == 0
