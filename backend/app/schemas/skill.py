# 기술 항목 관련 스키마

from pydantic import BaseModel, Field
from typing import Optional

class SkillCreate(BaseModel):
    name: str = Field(..., description="스킬 이름")
    category: Optional[str] = Field(None, description="카테고리")

class SkillResponse(BaseModel):
    id: int
    name: str
    category: Optional[str] = None

    class Config:
        from_attributes = True
