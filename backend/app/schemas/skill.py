# 기술 항목 관련 스키마

from pydantic import BaseModel, Field

class SkillCreate(BaseModel):
    name: str = Field(..., description="스킬 이름")

class SkillResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True
