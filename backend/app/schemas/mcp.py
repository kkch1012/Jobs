from pydantic import BaseModel, Field

class MessageIn(BaseModel):
    session_id: int = Field(..., description="채팅 세션 ID")
    message: str = Field(..., description="사용자 메시지")
