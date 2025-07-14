from beanie import Document
from datetime import datetime

class MCPMessage(Document):
    session_id: int
    role: str  # "user" 또는 "assistant"
    content: str
    created_at: datetime = datetime.utcnow()

    class Settings:
        name = "mcp_messages"
        indexes = [
            "session_id",
            "created_at",
            ("session_id", "created_at")
        ]
