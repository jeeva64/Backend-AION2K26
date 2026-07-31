from pydantic import BaseModel, ConfigDict


class CollegeDoc(BaseModel):
    model_config = ConfigDict(extra="allow")

    collegeId: str
    name: str
    state: str
    district: str
    registeredStatus: bool = False
