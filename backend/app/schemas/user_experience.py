from pydantic import BaseModel
from typing import Optional

class UserExperienceBase(BaseModel):
    type: Optional[str] = None
    name: Optional[str] = None
    period: Optional[str] = None
    description: Optional[str] = None

class UserExperienceCreate(UserExperienceBase):
    pass

class UserExperienceResponse(UserExperienceBase):
    id: int

    class Config:
        from_attributes = True
