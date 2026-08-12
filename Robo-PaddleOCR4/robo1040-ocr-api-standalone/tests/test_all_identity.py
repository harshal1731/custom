from app.ocr.extractors.form_1099_int import extract_1099_int
from app.ocr.extractors.w2 import extract_w2


AMEX_INT = """
AMERICAN EXPRESS NATIONAL BANK Savings
PAYER'S name, street address, city or town, state or province, country, ZIP
AMERICAN EXPRESS NATIONAL BANK
P.O.BOX 30384
SALT LAKE CITY, UT 84130-0384
1-800-446-6307
Form 1099-INT Interest
For calendar year 2024
PAYER'S TIN RECIPIENT'S TIN
11-2869526 XXX-XX-4860
RECIPIENT'S name, street address (including apt. no.), city or town
HEATH B TIMMERMAN
641 GATE POST DR
MOUNT PLEASANT, SC 29464
1 Interest income
$8986.68
2 Early withdrawal penalty
$0.00
Account number (see instructions)
XXXXXX6333
FATCA filing requirement
□
"""


GOLDMAN_INT = """
Goldman Sachs Form 1099-INT Savings Customer: Andrew Harmon, andrewhharmon@gmail.com
Jan 1 - Dec 31, 2024 Andrew Harmon 372 Evian Way Mt. Pleasant, SC 29464 USA
Tax Year: 2024 Account Number:910190526036 Tax ID Number:XXX-XX-2606
Payer's name: Goldman Sachs Bank USA
Payer's address: 200 West Street, New York, NY 10282
Payer's ID Number: 13-3571598
1 Interest Income $2653.39
2 Early withdrawal penalty $0.00
"""


W2_SAMPLE = """
c. Employers name, address, and ZiP code
I INS U Inc
925 Wappo R. Ste B
Charleston, sC 29407
e. Employee's name, address, and ZlP code
Thomas Masi Thomas Masi
PO Box 31058 PO Box 31058
Thomas Masi, SC 29417
XXX-XX-2930 2800.00 1365.22
57-1110444 2800.00 173.60
20230218-3 2800.00 40.60
SC 25411574-6 2800.00 113.68
Form W-2 2024
"""


def test_1099_int_irs_layout():
    f = extract_1099_int(AMEX_INT)
    assert f["Payer's TIN"] == "11-2869526"
    assert f["Recipient's TIN"] == "XXX-XX-4860"
    assert "TIMMERMAN" in (f["Recipient's Name"] or "")
    assert "GATE POST" in (f["Recipient's Street Address (including apt. no.)"] or "")
    assert "MOUNT PLEASANT" in (f["Recipient's city, state, country and Zip code"] or "")
    assert "BANK" in (f["PAYER'S name, address, and telephone"] or "").upper()
    assert f["Account Number"] == "XXXXXX6333"
    assert f["1 Interest Income"] == "8986.68"


def test_1099_int_broker_layout():
    f = extract_1099_int(GOLDMAN_INT)
    assert "Harmon" in (f["Recipient's Name"] or "")
    assert "372 Evian Way" in (f["Recipient's Street Address (including apt. no.)"] or "")
    assert "Mt. Pleasant" in (f["Recipient's city, state, country and Zip code"] or "")
    assert "Bank" in (f["PAYER'S name, address, and telephone"] or "")
    assert f["Account Number"] == "910190526036"
    assert f["1 Interest Income"] == "2653.39"
    assert f["5 Investment expenses"] in (None, "0.00")
    assert f["8 Tax-exempt interest"] in (None, "0.00")


def test_w2_still_good():
    f = extract_w2(W2_SAMPLE)
    assert f["Employee's first name and initial"] == "Thomas"
    assert f["Last name"] == "Masi"
