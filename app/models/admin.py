from pydantic import BaseModel, ConfigDict


class AdminDoc(BaseModel):
    model_config = ConfigDict(extra="allow")

    adminId: str
    name: str
    role: int  # 1 = Super Admin, 2 = Moderator
    password: str
