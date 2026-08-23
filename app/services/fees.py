"""Registration fee calculation — single source of truth.

Money is handled exclusively as integer paise. The backend is the only
authority for the unique student count and the payable amount; frontend
values are informational only and never trusted.
"""
import re
from urllib.parse import urlencode

from app.config.settings import settings
from app.utils.constants import CURRENCY

UTR_REGEX = re.compile(r"^[A-Za-z0-9]{8,22}$")


def calculate_registration_fee(unique_student_count: int) -> int:
    """Flat per-unique-student fee, integer paise (Rs.200 default)."""
    if unique_student_count < 0:
        raise ValueError("unique_student_count must be >= 0")
    return unique_student_count * settings.REGISTRATION_FEE_PER_STUDENT_PAISE


def paise_to_rupee_string(amount_paises: int) -> str:
    sign = "-" if amount_paises < 0 else ""
    amount_paises = abs(int(amount_paises))
    return f"{sign}{amount_paises // 100}.{amount_paises % 100:02d}"


def normalize_utr(utr: str | None) -> str | None:
    if utr is None:
        return None
    return utr.strip().upper() or None


def validate_utr(utr: str | None) -> str | None:
    """Return an error message for invalid UTRs, or None when valid."""
    normalized = normalize_utr(utr)
    if not normalized:
        return "UTR / transaction reference is required"
    if not UTR_REGEX.match(normalized):
        return "UTR must be 8-22 letters or digits with no spaces"
    return None


def build_upi_uri(leader_id: str, amount_paises: int) -> str | None:
    """Compose the UPI intent URI for the payment dialog's QR code.

    Returns None when UPI_VPA is not configured; the UI falls back to
    copyable text instructions in that case.
    """
    if not settings.UPI_VPA:
        return None
    params = {
        "pa": settings.UPI_VPA,
        "pn": settings.UPI_PAYEE_NAME or "AION 2K26",
        "am": paise_to_rupee_string(amount_paises),
        "tn": f"AION2K26-{leader_id}",
        "cu": CURRENCY,
    }
    return "upi://pay?" + urlencode(params)
