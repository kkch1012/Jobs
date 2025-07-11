from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class JobPostBase(BaseModel):
    title: str
    company_name: str
    size: Optional[str] = None
    address: Optional[str] = None
    job_required_skill_id: Optional[int] = None
    employment_type: Optional[str] = None
    applicant_type: str
    posting_date: datetime
    deadline: Optional[datetime] = None
    main_tasks: Optional[str] = None
    qualifications: Optional[str] = None
    preferences: Optional[str] = None
    tech_stack: Optional[str] = None
    required_skills: Optional[List[float]] = None
    preferred_skills: Optional[List[float]] = None
    essential_tech_stack: Optional[List[float]] = None


class JobPostCreate(JobPostBase):
    pass


class JobPostResponse(JobPostBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
