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
        if value != 2:
            raise ValueError("Only Moderator (role=2) can be created via this endpoint. Super Admin must be created via seeder.")
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


class AdminChangePasswordRequest(BaseModel):
    currentPassword: str | None = None
    newPassword: str | None = None
    confirmPassword: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _require_all_fields(cls, data):
        if isinstance(data, dict):
            missing = [field for field in ("currentPassword", "newPassword", "confirmPassword") if not data.get(field)]
            if missing:
                raise ValueError("All fields are required")
        return data

    @field_validator("newPassword", mode="after")
    @classmethod
    def _check_password_strength(cls, value):
        if len(value) < 8 or len(value) > 128:
            raise ValueError("Password must be 8-128 characters")
        if not any(c.isupper() for c in value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in value):
            raise ValueError("Password must contain at least one digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in value):
            raise ValueError("Password must contain at least one special character")
        if " " in value:
            raise ValueError("Password must not contain spaces")
        return value

    @model_validator(mode="after")
    def _check_passwords_match(self):
        if self.newPassword != self.confirmPassword:
            raise ValueError("New password and confirm password do not match")
        return self


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


class AdminChangePasswordResponse(APIResponse):
    pass


class UpdateCollegeRequest(BaseModel):
    collegeId: str | None = None
    name: str | None = None
    state: str | None = None
    district: str | None = None


class UpdateCollegeResponse(APIResponse):
    pass


class LeaderCollegeDeptsResponse(APIResponse):
    data: list[dict]
