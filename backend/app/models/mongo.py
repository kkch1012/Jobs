from beanie import Document
from datetime import datetime
from typing import Optional, Dict, Any

class MCPMessage(Document):
    session_id: int  # int로 변경
    role: str  # "user" 또는 "assistant"
    content: str
    created_at: datetime = datetime.utcnow()
    
    # MCP 관련 추가 필드
    tool_calls: Optional[list] = None  # 도구 호출 정보
    tool_results: Optional[list] = None  # 도구 실행 결과
    intent: Optional[Dict[str, Any] | list] = None  # 의도 분석 결과
    metadata: Optional[Dict[str, Any]] = None  # 추가 메타데이터
    
    class Settings:
        name = "mcp_messages"
        indexes = [
            "session_id",
            "created_at",
            ("session_id", "created_at")
        ]
