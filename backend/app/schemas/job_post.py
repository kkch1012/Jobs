from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class JobPostResponse(BaseModel):
    id: int
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
    required_skills: Optional[List[Any]] = None
    preferred_skills: Optional[List[Any]] = None
    main_tasks_skills: Optional[List[Any]] = None
    full_embedding: Optional[List[float]] = None
    created_at: datetime
    similarity: Optional[float] = None

    class Config:
        from_attributes = True
