from pydantic import BaseModel
from datetime import datetime
from typing import Optional


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


class JobPostCreate(JobPostBase):
    pass


class JobPostResponse(JobPostBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
