from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ChatSessionCreate(BaseModel):
    pass

class ChatSessionResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ChatSessionSimpleResponse(BaseModel):
    id: int
    updated_at: datetime

    class Config:
        from_attributes = True 