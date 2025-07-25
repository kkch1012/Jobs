from pydantic import BaseModel, Field
from datetime import datetime

class JobRoleCreate(BaseModel):
    name: str

class JobRoleResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class JobNameResponse(BaseModel):
    name: str

    class Config:
        from_attributes = True 