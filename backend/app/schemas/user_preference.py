from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel
from .job_post import JobPostBasicResponse

class UserPreferenceBase(BaseModel):
    job_post_id: int

class UserPreferenceCreate(UserPreferenceBase):
    pass

class UserPreferenceResponse(UserPreferenceBase):
    id: int
    user_id: int
    job_posting: JobPostBasicResponse

    class Config:
        from_attributes = True
