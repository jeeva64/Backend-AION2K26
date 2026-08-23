from pydantic import BaseModel, field_validator, model_validator

from app.schemas.common import APIResponse
from app.utils.validators import (
    validate_email,
    validate_field,
    validate_mobile_number,
    validate_name,
    validate_password,
)

_REQUIRED_FIELDS = (
    "name",
    "email",
    "mobilenumber",
    "department",
    "college",
    "shift",
    "password",
    "confirmpassword",
)


class LeaderRegisterRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    mobilenumber: str | int | None = None
    department: str | None = None
    college: str | None = None
    shift: str | None = None
    password: str | None = None
    confirmpassword: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _require_all_fields(cls, data):
        if isinstance(data, dict):
            missing = [field for field in _REQUIRED_FIELDS if not data.get(field)]
            if missing:
                raise ValueError("All fields are required")
        return data

    @field_validator("mobilenumber", mode="before")
    @classmethod
    def _coerce_mobile(cls, value):
        return str(value) if isinstance(value, int) else value

    @field_validator("name", mode="after")
    @classmethod
    def _check_name(cls, value):
        if value:
            if error := validate_name(value):
                raise ValueError(error)
        return value

    @field_validator("email", mode="after")
    @classmethod
    def _check_email(cls, value):
        if value:
            if error := validate_email(value):
                raise ValueError(error)
        return value

    @field_validator("mobilenumber", mode="after")
    @classmethod
    def _check_mobile(cls, value):
        if value:
            if error := validate_mobile_number(value):
                raise ValueError(error)
        return value

    @field_validator("department", mode="after")
    @classmethod
    def _check_department(cls, value):
        if value:
            if error := validate_field(value, "Department"):
                raise ValueError(error)
            if value.strip() not in ("cs", "it", "ai", "ds", "ca"):
                raise ValueError("Department must be one of: cs, it, ai, ds, ca")
        return value

    @field_validator("college", mode="after")
    @classmethod
    def _check_college(cls, value):
        if value:
            if error := validate_field(value, "College"):
                raise ValueError(error)
        return value

    @field_validator("shift", mode="after")
    @classmethod
    def _check_shift(cls, value):
        if value:
            if value.strip() not in ("1", "2"):
                raise ValueError("Shift must be 1 or 2")
        return value

    @field_validator("password", mode="after")
    @classmethod
    def _check_password(cls, value):
        if value:
            if error := validate_password(value):
                raise ValueError(error)
        return value

    @model_validator(mode="after")
    @classmethod
    def _check_passwords_match(cls, model):
        if model.password and model.confirmpassword and model.password != model.confirmpassword:
            raise ValueError("Passwords do not match")
        return model


class LeaderLoginRequest(BaseModel):
    email: str | None = None
    password: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _require_credentials(cls, data):
        if isinstance(data, dict):
            if not data.get("email") or not data.get("password"):
                raise ValueError("Email and Password required")
        return data


class ParticipantIn(BaseModel):
    name: str | None = None
    registerNumber: str | None = None
    mobile: str | int | None = None
    degree: str | None = None
    foodPreference: str | None = None

    @field_validator("mobile", mode="before")
    @classmethod
    def _coerce_mobile(cls, value):
        return str(value) if isinstance(value, int) else value


class RegisterTeamRequest(BaseModel):
    leaderId: str | None = None
    event: str | None = None
    participants: list[ParticipantIn] | None = None

    @model_validator(mode="before")
    @classmethod
    def _require_fields(cls, data):
        if isinstance(data, dict):
            if not data.get("leaderId") or not data.get("event") or not data.get("participants"):
                raise ValueError("leaderId, event, and a non-empty participants array are required")
        return data


class GetCandidatesRequest(BaseModel):
    user_id: str | None = None


class LeaderRegisterResponse(APIResponse):
    userid: str


class LeaderLoginResponse(APIResponse):
    userid: str
    name: str
    token: str


class RegisterTeamResponse(APIResponse):
    created: int
    updated: int
    uniqueStudents: int | None = None
    amountDuePaises: int | None = None
    currency: str | None = None
    upiUri: str | None = None
    paymentStatus: str | None = None


class GetCandidatesResponse(APIResponse):
    totalStudents: int
    registeredEvents: list[str]
    data: list[dict]


class StatsResponse(APIResponse):
    stats: dict


class AddCollegeResponse(APIResponse):
    count: int


class GetCollegeResponse(APIResponse):
    data: list[dict]
