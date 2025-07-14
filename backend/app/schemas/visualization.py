from pydantic import BaseModel
from typing import List

class WeeklySkillStat(BaseModel):
    year: int
    week: int
    skill: str
    count: int

    class Config:
        from_attributes = True

class ResumeSkillComparison(BaseModel):
    skill: str
    count: int
    status: str  # '강점' or '약점'
    year: int
    week: int

    class Config:
        from_attributes = True 