from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database.PostgreSQL import Base
from app.models.user import User

class UserSkill(Base):
    __tablename__ = "user_skills"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)

    proficiency = Column(String, nullable=False)  # 예: 초급, 중급, 고급

    user = relationship("User", back_populates="user_skills")
    skill = relationship("Skill", back_populates="user_skills")
