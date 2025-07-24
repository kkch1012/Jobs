from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.PostgreSQL import Base

class TodoList(Base):
    __tablename__ = "todo_lists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)                    # 할 일 제목
    description = Column(Text, nullable=True)                      # 할 일 상세 설명
    is_completed = Column(Boolean, default=False, nullable=False)  # 완료 여부
    priority = Column(String(20), default="medium", nullable=False) # 우선순위 (low, medium, high)
    due_date = Column(DateTime(timezone=True), nullable=True)      # 마감일
    category = Column(String(100), nullable=True)                  # 카테고리 (예: "스킬 학습", "자격증", "프로젝트")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 제약조건
    __table_args__ = (
        CheckConstraint("priority IN ('low', 'medium', 'high')", name="chk_todo_lists_priority"),
        CheckConstraint("LENGTH(title) >= 1 AND LENGTH(title) <= 255", name="chk_todo_lists_title_length"),
        CheckConstraint("LENGTH(category) <= 100", name="chk_todo_lists_category_length"),
    )

    # Relationship
    user = relationship("User", back_populates="todo_lists") 