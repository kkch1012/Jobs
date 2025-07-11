from pydantic import BaseModel

class MessageIn(BaseModel):
    session_id: str
    message: str
