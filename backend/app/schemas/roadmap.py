from pydantic import BaseModel, Field
from datetime import datetime

# 로드맵 생성 요청 모델
class RoadmapBase(BaseModel):
    name: str = Field(..., description="로드맵 이름 (예: AI 부트캠프)")
    type: str = Field(..., description="로드맵 유형 (예: 부트캠프, 코스)")
    description: str = Field(..., description="로드맵 설명")
    start_date: datetime = Field(..., description="시작일")
    end_date: datetime = Field(..., description="마감일")
    status: str = Field(..., description="진행 상태 (예: 진행 중, 완료 등)")

class RoadmapCreate(RoadmapBase):
    pass

class RoadmapUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    description: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str | None = None

class RoadmapResponse(RoadmapBase):
    id: int

    class Config:
        from_attributes = True 