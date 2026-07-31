from typing import Any

from pydantic import BaseModel


def success(message: str, **extra: Any) -> dict[str, Any]:
    """Standard success envelope: {"success": true, "message": ..., **extra}."""
    return {"success": True, "message": message, **extra}


class APIResponse(BaseModel):
    """Base envelope for every successful response."""

    success: bool = True
    message: str


class HealthResponse(APIResponse):
    pass
