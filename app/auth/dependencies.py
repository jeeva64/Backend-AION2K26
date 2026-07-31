import jwt
from fastapi import Header

from app.exceptions.api_error import APIError
from app.auth.security import decode_access_token


def _extract_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise APIError(401, "Access denied. No token provided.")
    return authorization.split(" ", 1)[1].strip()


def _decode(token: str) -> dict:
    try:
        return decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise APIError(401, "Session expired. Please login again.")
    except jwt.InvalidTokenError:
        raise APIError(401, "Invalid token.")


def get_current_user(authorization: str | None = Header(None)) -> dict:
    payload = _decode(_extract_token(authorization))
    if payload.get("role") != "user":
        raise APIError(403, "Access denied. User only.")
    return payload


def get_current_admin(authorization: str | None = Header(None)) -> dict:
    payload = _decode(_extract_token(authorization))
    if payload.get("role") != "admin":
        raise APIError(403, "Access denied. Admin only.")
    return payload


def get_current_super_admin(authorization: str | None = Header(None)) -> dict:
    payload = _decode(_extract_token(authorization))
    if payload.get("role") != "admin" or payload.get("adminRole") != 1:
        raise APIError(403, "Access denied. Super Admin only.")
    return payload
