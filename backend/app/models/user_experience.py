from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database.PostgreSQL import Base

class UserExperience(Base):
    __tablename__ = "user_experiences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))

    type = Column(String, nullable=True)          # 경험형태
    name = Column(String, nullable=True)          # 경험 이름
    period = Column(String, nullable=True)        # 기간
    description = Column(String, nullable=True)   # 설명

    user = relationship("User", back_populates="experiences")
