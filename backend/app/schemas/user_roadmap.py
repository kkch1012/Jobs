from pydantic import BaseModel

class UserRoadmapBase(BaseModel):
    user_id: int
    roadmaps_id: int

class UserRoadmapCreate(UserRoadmapBase):
    pass

class UserRoadmapResponse(UserRoadmapBase):
    id: int

    class Config:
        from_attributes = True  # Pydantic v2 기준
