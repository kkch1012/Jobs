from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database.PostgreSQL import Base

class UserSkill(Base):
    __tablename__ = "user_skills"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="CASCADE"))
    proficiency = Column(String, nullable=False)  # 예: 초급, 중급, 고급

    user = relationship("User", back_populates="user_skills")
    skill = relationship("Skill", back_populates="users")
