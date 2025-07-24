from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class TodoListBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="할 일 제목")
    description: Optional[str] = Field(None, description="할 일 상세 설명")
    is_completed: bool = Field(False, description="완료 여부")
    priority: str = Field("medium", description="우선순위 (low, medium, high)")
    due_date: Optional[datetime] = Field(None, description="마감일")
    category: Optional[str] = Field(None, max_length=100, description="카테고리")

class TodoListCreate(TodoListBase):
    pass

class TodoListUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="할 일 제목")
    description: Optional[str] = Field(None, description="할 일 상세 설명")
    is_completed: Optional[bool] = Field(None, description="완료 여부")
    priority: Optional[str] = Field(None, description="우선순위 (low, medium, high)")
    due_date: Optional[datetime] = Field(None, description="마감일")
    category: Optional[str] = Field(None, max_length=100, description="카테고리")

class TodoListResponse(TodoListBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TodoListListResponse(BaseModel):
    todo_lists: List[TodoListResponse]
    total_count: int
    completed_count: int
    pending_count: int 