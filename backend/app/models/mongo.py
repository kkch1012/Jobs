from beanie import Document
from datetime import datetime

class MCPMessage(Document):
    session_id: str
    role: str  # "user" 또는 "assistant"
    content: str
    created_at: datetime = datetime.utcnow()
