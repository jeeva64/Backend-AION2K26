import pytest

from app.utils.validators import (
    clean_mobile_number,
    clean_participant_mobile,
    validate_email,
    validate_field,
    validate_mobile_number,
    validate_name,
    validate_password,
)


def test_valid_password():
    assert validate_password("Passw0rd!") is None


@pytest.mark.parametrize(
    "password,expected",
    [
        ("short1!", "Password must be at least 8 characters long"),
        ("NoDigits!", "Password must contain at least one number"),
        ("alllower1!", "Password must contain at least one uppercase letter"),
        ("ALLUPPER1!", "Password must contain at least one lowercase letter"),
        ("NoSpecial1", "Password must contain at least one special character (!@#$%^&*...)"),
        ("Space1! pass", "Password cannot contain spaces"),
    ],
)
def test_invalid_passwords(password, expected):
    assert validate_password(password) == expected


def test_email():
    assert validate_email("a@b.co") is None
    assert validate_email("bad-email") == "Please enter a valid email address"
    assert validate_email("") == "Email is required"


def test_mobile():
    assert validate_mobile_number("9876543210") is None
    assert validate_mobile_number("1234567890") == "Please enter a valid 10-digit mobile number starting with 6-9"
    assert validate_mobile_number("") == "Mobile number is required"
    assert clean_mobile_number("+91 98765-43210") == "919876543210"


def test_name():
    assert validate_name("Arjun Kumar") is None
    assert validate_name("A") == "Name must be at least 2 characters long"
    assert validate_name("Name123") == "Name can only contain letters, spaces, dots, and hyphens"


def test_field():
    assert validate_field("cs", "Department") is None
    assert validate_field("c", "Department") == "Department must be at least 2 characters long"


def test_clean_participant_mobile():
    assert clean_participant_mobile("98765 43210") == "9876543210"
    assert clean_participant_mobile("98765-43210") == "9876543210"
