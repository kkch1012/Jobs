from pydantic import BaseModel
from typing import List

class WeeklySkillStat(BaseModel):
    week_day: str
    skill: str
    count: int

    class Config:
        from_attributes = True

class ResumeSkillComparison(BaseModel):
    skill: str
    count: int
    status: str  # '강점' or '약점'
    week_day: str

    class Config:
        from_attributes = True 