from pydantic import BaseModel
from .roadmap import RoadmapResponse

class UserRoadmapBase(BaseModel):
    roadmaps_id: int

class UserRoadmapCreate(UserRoadmapBase):
    pass

class UserRoadmapResponse(UserRoadmapBase):
    id: int
    user_id: int
    roadmap: RoadmapResponse  # RoadmapResponse 사용

    class Config:
        from_attributes = True  # Pydantic v2 기준
