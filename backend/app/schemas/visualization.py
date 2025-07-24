from pydantic import BaseModel
from typing import List, Optional
from datetime import date

class WeeklySkillStat(BaseModel):
    week: int
    date: date
    skill: str
    count: int

    class Config:
        from_attributes = True

class DailySkillStatWithRank(BaseModel):
    week: int
    date: date
    skill: str
    count: int
    rank: Optional[int] = None  # 해당 날짜에서의 순위 (1부터 시작)

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