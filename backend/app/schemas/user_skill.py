from pydantic import BaseModel, Field

class UserSkillBase(BaseModel):
    proficiency: str = Field(..., description="숙련도 (예: 초급, 중급, 고급)")

# 입력용: 프론트에서 skill_name과 proficiency를 보냄
class UserSkillCreate(BaseModel):
    skill_name: str = Field(..., description="스킬 이름")
    proficiency: str = Field(..., description="숙련도 (예: 초급, 중급, 고급)")

# 응답용: DB 저장 후 id, user_id, skill_id, proficiency 반환
class UserSkillResponse(UserSkillBase):
    id: int
    user_id: int
    skill_id: int

    class Config:
        from_attributes = True
