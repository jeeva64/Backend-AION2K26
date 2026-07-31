from pydantic import BaseModel, ConfigDict


class UserDoc(BaseModel):
    model_config = ConfigDict(extra="allow")

    userid: str
    name: str
    email: str
    mobilenumber: str
    department: str
    college: str
    shift: str
    password: str
