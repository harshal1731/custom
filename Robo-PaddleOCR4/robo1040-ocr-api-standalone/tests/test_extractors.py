import re

from app.ocr.extractors.w2 import extract_w2


SAMPLE = """
Copy B--To Be Filed With Employee's FEDERAL Tax Return
a. Employee's social security number 1. Wages, tips, other compensation 2. Federal income tax withheld
XXX-XX-2930 2800.00 1365.22
b. Employer ID number (EIN) 3. Social security wages 4. Social security tax withheld
57-1110444 2800.00 173.60
d. Control number 5. Medicare wages and tips 6. Medicare tax withheld
20230218-3 2800.00 40.60
c. Employers name, address, and ZiP code
I INS U Inc
925 Wappo R. Ste B
Charleston, sC 29407
e. Employee's name, address, and ZlP code
Thomas Masi Thomas Masi
PO Box 31058 PO Box 31058
Thomas Masi, SC 29417 mhomas Masi, SC 29417
15.State Employer's state ID number 16. State wages, tips, etc. 17.State income tax
SC 25411574-6 2800.00 113.68
Form W-2 Wage and Tax Statement 2024
Copy 2--To Be Filed With Employee's State
XXX-XX-2930 2800.00 1365.22
"""


def test_w2_key_values():
    fields = extract_w2(SAMPLE)
    assert fields["Year"] == "2024"
    assert fields["Employee's social security number"] == "XXX-XX-2930"
    assert fields["Employer identification number (EIN)"] == "57-1110444"
    assert fields["1 Wages, tips, other compensation"] == "2800.00"
    assert fields["2 Federal income tax withheld"] == "1365.22"
    assert fields["3 Social security wages"] == "2800.00"
    assert fields["4 Social security tax withheld"] == "173.60"
    assert fields["5 Medicare wages and tips"] == "2800.00"
    assert fields["6 Medicare tax withheld"] == "40.60"
    assert fields["Control number"] == "20230218-3"
    assert fields["16 State wages, tips, etc."] == "2800.00"
    assert fields["17 State income tax"] == "113.68"
    assert fields["Employee's first name and initial"] == "Thomas"
    assert fields["Last name"] == "Masi"
    assert fields["Employee's address and ZIP code"]
    assert re.search(r"P\.?O\.?\s*Box\s*31058", fields["Employee's address and ZIP code"], re.I)
    assert "I INS U Inc" in fields["Employer's name, address, and ZIP code"]
