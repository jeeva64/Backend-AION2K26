from pydantic import BaseModel, field_validator, model_validator

from app.schemas.common import APIResponse


class AdminRegisterRequest(BaseModel):
    adminId: str | None = None
    name: str | None = None
    role: int | None = None
    password: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _require_all_fields(cls, data):
        if isinstance(data, dict):
            missing = [field for field in ("adminId", "name", "role", "password") if not data.get(field)]
            if missing:
                raise ValueError("All fields are required")
        return data

    @field_validator("role", mode="after")
    @classmethod
    def _check_role(cls, value):
        if value not in (1, 2):
            raise ValueError("Role must be 1 (Super Admin) or 2 (Moderator)")
        return value


class AdminLoginRequest(BaseModel):
    adminId: str | None = None
    password: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _require_credentials(cls, data):
        if isinstance(data, dict):
            if not data.get("adminId") or not data.get("password"):
                raise ValueError("All fields are required")
        return data


class ViewTeamRequest(BaseModel):
    college: str | None = None
    department: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _require_fields(cls, data):
        if isinstance(data, dict):
            if not data.get("college") or not data.get("department"):
                raise ValueError("All fields are required")
        return data


class ViewEventRegsRequest(BaseModel):
    eventName: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _require_event(cls, data):
        if isinstance(data, dict):
            if not data.get("eventName"):
                raise ValueError("Event name required")
        return data


class AdminRegisterResponse(APIResponse):
    pass


class AdminLoginResponse(APIResponse):
    role: int
    token: str


class ViewTeamResponse(APIResponse):
    data: list[dict]


class ViewEventRegsResponse(APIResponse):
    event: str
    totalTeams: int
    data: list[dict]


class DeleteTeamResponse(APIResponse):
    deletedCount: int


class DeleteTeamByEventResponse(APIResponse):
    updatedCount: int
    deletedCount: int


class DashboardStatsResponse(APIResponse):
    stats: dict
