from pydantic import BaseModel
from typing import List
from datetime import date

class WeeklySkillStat(BaseModel):
    week: int
    date: date
    skill: str
    count: int

    class Config:
        from_attributes = True

class ResumeSkillComparison(BaseModel):
    skill: str
    count: int
    status: str
    week: int
    date: date

    class Config:
        from_attributes = True 