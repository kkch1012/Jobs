from pydantic import BaseModel, Field

class UserSkillBase(BaseModel):
    skill_id: int = Field(..., description="연결할 스킬 ID")
    proficiency: str = Field(..., description="숙련도 (예: 초급, 중급, 고급)")

class UserSkillCreate(UserSkillBase):
    pass

class UserSkillResponse(UserSkillBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True
