from pydantic import BaseModel, model_validator

from app.schemas.common import APIResponse


class RejectPaymentRequest(BaseModel):
    reason: str | None = None

    @model_validator(mode="after")
    def _require_reason(self):
        if not self.reason or not self.reason.strip():
            raise ValueError("Rejection reason is required")
        if len(self.reason.strip()) > 500:
            raise ValueError("Rejection reason must be 500 characters or fewer")
        return self


class SubmitProofResponse(APIResponse):
    paymentId: int
    paymentStatus: str


class MyPaymentsResponse(APIResponse):
    uniqueStudents: int
    amountDuePaises: int
    upiUri: str | None = None
    data: dict | None = None


class PaymentListResponse(APIResponse):
    count: int
    data: list[dict]


class PaymentDetailResponse(APIResponse):
    data: dict
    audit: list[dict]


class PaymentProofResponse(APIResponse):
    url: str
    expiresIn: int
    mimeType: str | None = None
    originalFilename: str | None = None


class PaymentActionResponse(APIResponse):
    paymentStatus: str
