from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict, Any

# ===== 공통 필드 BaseModel =====
class CommonBase(BaseModel):
    name: str = Field(..., description="이름")
    type: str = Field(..., description="유형")
    skill_description: List[str] | Dict[str, Any] = Field(..., description="기술명")
    company: Optional[str] = Field(None, description="회사명")

# ===== 공통 Update BaseModel =====
class CommonUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    skill_description: Optional[List[str] | Dict[str, Any]] = None
    company: Optional[str] = None

# ===== 부트캠프용 스키마 =====
class RoadmapBase(CommonBase):
    start_date: Optional[datetime] = Field(None, description="시작일")
    end_date: Optional[datetime] = Field(None, description="마감일")
    status: str = Field(..., description="진행 상태 (예: 진행 중, 완료 등)")
    deadline: Optional[datetime] = Field(None, description="마감일(선택)")
    location: Optional[str] = Field(None, description="장소")
    onoff: Optional[str] = Field(None, description="온/오프/온오프")
    participation_time: Optional[str] = Field(None, description="참여 시간")
    program_course: Optional[str] = Field(None, description="프로그램/코스명")

class RoadmapCreate(RoadmapBase):
    pass

class RoadmapUpdate(CommonUpdate):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = None
    deadline: Optional[datetime] = None
    location: Optional[str] = None
    onoff: Optional[str] = None
    participation_time: Optional[str] = None
    program_course: Optional[str] = None

class RoadmapResponse(RoadmapBase):
    id: int

    class Config:
        from_attributes = True

# ===== 강의용 스키마 =====
class CourseBase(CommonBase):
    link: Optional[str] = Field(None, description="강의 링크")
    price: Optional[str] = Field(None, description="가격")

class CourseCreate(CourseBase):
    pass

class CourseUpdate(CommonUpdate):
    link: Optional[str] = None
    price: Optional[str] = None

class CourseResponse(CourseBase):
    id: int

    class Config:
        from_attributes = True 