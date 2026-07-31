import re

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
_MOBILE_REGEX = re.compile(r"^[6-9]\d{9}$")
_NAME_REGEX = re.compile(r"^[a-zA-Z\s.\-']+$")
_PASSWORD_SPECIAL = re.compile(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]")


def validate_password(password: str | None) -> str | None:
    if not password or len(password) < 8:
        return "Password must be at least 8 characters long"
    if len(password) > 128:
        return "Password must not exceed 128 characters"
    if re.search(r"\s", password):
        return "Password cannot contain spaces"
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter"
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one number"
    if not _PASSWORD_SPECIAL.search(password):
        return "Password must contain at least one special character (!@#$%^&*...)"
    return None


def validate_email(email: str | None) -> str | None:
    if not email:
        return "Email is required"
    if not _EMAIL_REGEX.match(email.strip()):
        return "Please enter a valid email address"
    return None


def validate_mobile_number(mobilenumber) -> str | None:
    if not mobilenumber:
        return "Mobile number is required"
    if not _MOBILE_REGEX.match(clean_mobile_number(mobilenumber)):
        return "Please enter a valid 10-digit mobile number starting with 6-9"
    return None


def clean_mobile_number(mobilenumber) -> str:
    return re.sub(r"\D", "", str(mobilenumber))


def clean_participant_mobile(mobile: str) -> str:
    return re.sub(r"[\s\-]", "", str(mobile))


def validate_name(name: str | None) -> str | None:
    if not name or len(name.strip()) < 2:
        return "Name must be at least 2 characters long"
    if len(name.strip()) > 100:
        return "Name must not exceed 100 characters"
    if not _NAME_REGEX.match(name.strip()):
        return "Name can only contain letters, spaces, dots, and hyphens"
    return None


def validate_field(value: str | None, field_name: str) -> str | None:
    if not value or len(value.strip()) < 2:
        return f"{field_name} must be at least 2 characters long"
    if len(value.strip()) > 100:
        return f"{field_name} must not exceed 100 characters"
    return None
