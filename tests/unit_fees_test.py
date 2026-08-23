"""Unit tests for fee calculation, UTR handling and UPI URI building."""
import pytest

from app.config.settings import settings
from app.services.fees import (
    build_upi_uri,
    calculate_registration_fee,
    normalize_utr,
    paise_to_rupee_string,
    validate_utr,
)


def test_fee_flat_per_student(monkeypatch):
    monkeypatch.setattr(settings, "REGISTRATION_FEE_PER_STUDENT_PAISE", 20000)
    assert calculate_registration_fee(0) == 0
    assert calculate_registration_fee(1) == 20000
    assert calculate_registration_fee(15) == 300000


def test_fee_rejects_negative():
    with pytest.raises(ValueError):
        calculate_registration_fee(-1)


def test_paise_to_rupee_string():
    assert paise_to_rupee_string(20000) == "200.00"
    assert paise_to_rupee_string(19999) == "199.99"
    assert paise_to_rupee_string(5) == "0.05"
    assert paise_to_rupee_string(0) == "0.00"
    assert paise_to_rupee_string(-250) == "-2.50"


def test_normalize_and_validate_utr():
    assert normalize_utr("  abcd1234abcd  ") == "ABCD1234ABCD"
    assert normalize_utr(None) is None
    assert normalize_utr("   ") is None

    assert validate_utr("123456789012") is None
    assert validate_utr("ABCD1234ABCD") is None
    assert validate_utr(None) is not None
    assert validate_utr("") is not None
    assert validate_utr("   ") is not None
    assert validate_utr("short12") is not None          # <8 chars
    assert validate_utr("x" * 23) is not None           # >22 chars
    assert validate_utr("has space 12345") is not None
    assert validate_utr("bad!symbol1234") is not None


def test_upi_uri_contains_required_params(monkeypatch):
    monkeypatch.setattr(settings, "UPI_VPA", "aion2k26@upi")
    monkeypatch.setattr(settings, "UPI_PAYEE_NAME", "AION 2K26")
    uri = build_upi_uri("LD123", 40000)
    assert uri is not None and uri.startswith("upi://pay?")
    assert "pa=aion2k26%40upi" in uri or "pa=aion2k26@upi" in uri
    assert "am=400.00" in uri
    assert "cu=INR" in uri
    assert "tn=AION2K26-LD123" in uri


def test_upi_uri_none_without_vpa(monkeypatch):
    monkeypatch.setattr(settings, "UPI_VPA", "")
    assert build_upi_uri("LD123", 40000) is None
