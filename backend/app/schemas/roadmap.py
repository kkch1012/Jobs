from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict, Any

# 로드맵 생성 요청 모델
class RoadmapBase(BaseModel):
    name: str = Field(..., description="로드맵 이름 (예: AI 부트캠프)")
    type: str = Field(..., description="로드맵 유형 (예: 부트캠프, 코스)")
    skill_description: List[str] | Dict[str, Any] = Field(..., description="로드맵 기술명")
    start_date: Optional[datetime] = Field(None, description="시작일")
    end_date: Optional[datetime] = Field(None, description="마감일")
    status: str = Field(..., description="진행 상태 (예: 진행 중, 완료 등)")
    deadline: Optional[datetime] = Field(None, description="마감일(선택)")
    location: Optional[str] = Field(None, description="장소")
    onoff: Optional[str] = Field(None, description="온/오프/온오프")
    participation_time: Optional[str] = Field(None, description="참여 시간")
    company: Optional[str] = Field(None, description="회사명")
    program_course: Optional[str] = Field(None, description="프로그램/코스명")

class RoadmapCreate(RoadmapBase):
    pass

class RoadmapUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    skill_description: Optional[List[str] | Dict[str, Any]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = None
    deadline: Optional[datetime] = None
    location: Optional[str] = None
    onoff: Optional[str] = None
    participation_time: Optional[str] = None
    company: Optional[str] = None
    program_course: Optional[str] = None

class RoadmapResponse(RoadmapBase):
    id: int

    class Config:
        from_attributes = True 