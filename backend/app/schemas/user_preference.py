from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class JobPostBase(BaseModel):
    title: str
    company_name: str
    size: str
    address: str
    job_required_skill_id: Optional[int]
    employment_type: Optional[str] = None
    applicant_type: str
    posting_date: datetime
    deadline: datetime
    main_tasks: Optional[str] = None
    qualifications: Optional[str] = None
    preferences: Optional[str] = None
    tech_stack: Optional[str] = None
    required_skills: Optional[str] = None
    preferred_skills: Optional[str] = None
    essential_tech_stack: Optional[str] = None

    class Config:
        from_attributes = True

class UserPreferenceBase(BaseModel):
    job_post_id: int

class UserPreferenceCreate(UserPreferenceBase):
    pass

class UserPreferenceResponse(UserPreferenceBase):
    id: int
    user_id: int
    job_posting: JobPostBase  # 여기서 JobPostBase를 포함

    class Config:
        from_attributes = True
