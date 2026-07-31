from pydantic import BaseModel, ConfigDict


class EventRegistrationDoc(BaseModel):
    model_config = ConfigDict(extra="allow")

    leaderId: str
    name: str
    registerNumber: str
    mobile: str
    college: str
    department: str
    degree: str
    foodPreference: str
    event1: str
    slot1: str
    event2: str | None = None
    slot2: str | None = None
