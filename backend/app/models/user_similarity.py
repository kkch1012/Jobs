from sqlalchemy import Float, Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.PostgreSQL import Base

class UserSimilarity(Base):
    __tablename__ = "user_similarity"

    id = Column(Integer, primary_key=True, index=True)  # 유저유사도ID
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_post_id = Column(Integer, ForeignKey("job_posts.id", ondelete="CASCADE"), nullable=False)
    similarity = Column(Float, nullable=False)  # 유사도,적합도 (예: 0.856)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # 생성 시간

UserSimilarity.job_post = relationship("JobPost", back_populates="user_similarities")
UserSimilarity.user = relationship("User", back_populates="user_similarities")