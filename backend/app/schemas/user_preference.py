from pydantic import BaseModel

class UserPreferenceBase(BaseModel):
    job_post_id: int

class UserPreferenceCreate(UserPreferenceBase):
    pass

class UserPreferenceResponse(UserPreferenceBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True  # orm_mode (v1) → from_attributes (v2)
