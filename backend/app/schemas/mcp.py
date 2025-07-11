from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class MessageIn(BaseModel):
    session_id: str = Field(..., description="채팅 세션 ID")
    message: str = Field(..., description="사용자 메시지")

class MCPIntent(BaseModel):
    router: str = Field(..., description="호출할 라우터 경로")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="라우터 파라미터")

class MCPMessageOut(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    created_at: datetime

class MCPResponse(BaseModel):
    message: str = Field(..., description="AI 응답 메시지")
    session_id: str = Field(..., description="채팅 세션 ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class MCPToolCall(BaseModel):
    tool_name: str = Field(..., description="호출할 도구 이름")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="도구 파라미터")

class MCPContext(BaseModel):
    user_id: Optional[int] = Field(None, description="사용자 ID")
    session_id: str = Field(..., description="세션 ID")
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list, description="대화 히스토리")
    available_tools: List[str] = Field(default_factory=list, description="사용 가능한 도구 목록")
