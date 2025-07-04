from pydantic import BaseModel, EmailStr, Field
from datetime import date, datetime
from typing import Optional, List, Dict

# 회원가입 시 받을 필드
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nickname: str
    name: str
    phone_number: str
    birth_date: date
    gender: str

# 사용자 응답용
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    nickname: str
    name: str
    phone_number: str
    created_at: datetime

    class Config:
        orm_mode = True

# 이력서(프로필) 업데이트용
class ResumeUpdate(BaseModel):
    university: Optional[str] = None
    major: Optional[str] = None
    gpa: Optional[float] = None
    education_status: Optional[str] = None
    degree: Optional[str] = None
    language_score: Optional[Dict[str, int]] = Field(default_factory=dict)
    desired_job: Optional[str] = None
    experience: Optional[List[dict]] = Field(default_factory=list)
    working_year: Optional[str] = "신입"

# 이력서 응답용
class ResumeResponse(ResumeUpdate):
    id: int

    class Config:
        orm_mode = True

# 사용자 보유 기술 입력용
class UserSkillCreate(BaseModel):
    skill_id: int
    proficiency: str

# 사용자 보유 기술 응답용
class UserSkillResponse(UserSkillCreate):
    id: int

    class Config:
        orm_mode = True

# 사용자 자격증 입력용
class UserCertificateCreate(BaseModel):
    certificate_id: int
    acquired_date: date

# 사용자 자격증 응답용
class UserCertificateResponse(UserCertificateCreate):
    id: int

    class Config:
        orm_mode = True