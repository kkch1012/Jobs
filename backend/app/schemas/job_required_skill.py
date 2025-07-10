from pydantic import BaseModel, Field
from datetime import datetime

class JobRequiredSkillCreate(BaseModel):
    name: str

class JobRequiredSkillResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class JobNameResponse(BaseModel):
    name: str

    class Config:
        from_attributes = True