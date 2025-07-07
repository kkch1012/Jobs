from pydantic import BaseModel, EmailStr, Field
from datetime import date, datetime
from typing import Optional, List, Dict
from app.schemas.user_skill import UserSkillResponse,UserSkillCreate
from app.schemas.user_certificate import UserCertificateResponse,UserCertificateCreate

# ID 기반 회원가입용
class UserCreateID(BaseModel):
    email: str
    password: str
    confirm_password: str
    nickname: str
    name: str
    phone_number: str
    birth_date: date
    gender: str

# 이메일 기반 (소셜 로그인) 회원가입용
class UserCreateEmail(BaseModel):
    email: EmailStr
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
        from_attributes = True

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
    
    skills: Optional[List[UserSkillCreate]] = None
    certificates: Optional[List[UserCertificateCreate]] = None

# 이력서 응답용
class UserResumeResponse(BaseModel):
    id: int
    email: EmailStr
    nickname: str
    name: str
    phone_number: str

    university: Optional[str] = None
    major: Optional[str] = None
    gpa: Optional[float] = None
    education_status: Optional[str] = None
    degree: Optional[str] = None
    language_score: Optional[dict] = Field(default_factory=dict)
    desired_job: Optional[str] = None
    experience: Optional[List[dict]] = Field(default_factory=list)
    working_year: Optional[str] = "신입"

    skills: List[UserSkillResponse] = []
    certificates: List[UserCertificateResponse] = []

    class Config:
        from_attributes = True