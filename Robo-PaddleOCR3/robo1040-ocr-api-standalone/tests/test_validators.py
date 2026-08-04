from app.ocr.validators import validate_fields


def test_rejects_boilerplate_recipient_name():
    fields = validate_fields(
        "1099-INT",
        {"Recipient's Name": "nished to the IRS. If you are required"},
    )
    assert fields["Recipient's Name"] is None


def test_normalizes_tin_and_money():
    fields = validate_fields(
        "1099-INT",
        {
            "Recipient's TIN": "***-**-4453",
            "Payer's TIN": "560223230",
            "1 Interest Income": "$1,234.56",
        },
    )
    assert fields["Recipient's TIN"] == "XXX-XX-4453"
    assert fields["Payer's TIN"] == "56-0223230"
    assert fields["1 Interest Income"] == "1234.56"
