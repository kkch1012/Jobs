from beanie import Document
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class MCPMessage(Document):
    session_id: int
    role: str  # "user" or "assistant"
    content: str
    created_at: datetime

    class Settings:
        name = "mcp_messages"

class IntentItem(BaseModel):
    intent: str
    parameters: Dict[str, Any]
    description: str

class MultipleIntentSession(Document):
    session_id: int
    intents: List[IntentItem]
    created_at: datetime
    executed_count: int = 0  # 실행된 작업 수

    class Settings:
        name = "multiple_intent_sessions"
