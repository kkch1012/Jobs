from pydantic import BaseModel, Field
from typing import Optional

class UserSkillBase(BaseModel):
    proficiency: str = Field(..., description="숙련도 (예: 초급, 중급, 고급)")

# 입력용: 프론트에서 skill_name과 proficiency를 보냄
class UserSkillCreate(UserSkillBase):
    skill_name: str = Field(..., description="스킬 이름")

# 응답용: DB 저장 후 skill_name, proficiency 반환
class UserSkillResponse(UserSkillCreate):
    skill_id: Optional[int] = None

    class Config:
        from_attributes = True
