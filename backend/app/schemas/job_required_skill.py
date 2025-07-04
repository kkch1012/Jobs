from pydantic import BaseModel, Field
from datetime import datetime

class JobRequiredSkillCreate(BaseModel):
    job_role_id: int = Field(..., description="직무 ID")
    name: str = Field(..., description="직무 이름")
    skill: str = Field(..., description="직무에 필요한 기술")
    skill_type: str = Field(..., description="요구 유형 (예: 필수, 우대 등)")

class JobRequiredSkillResponse(BaseModel):
    job_role_id: int
    name: str
    skill: str
    skill_type: str
    job_date: datetime

    class Config:
        from_attributes = True
