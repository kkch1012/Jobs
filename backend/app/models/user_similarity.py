from sqlalchemy import VARCHAR, Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.database.PostgreSQL import Base

class UserSimilarity(Base):
    __tablename__ = "user_similarity"

    id = Column(Integer, primary_key=True, index=True)  # 유저유사도ID
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_post_id = Column(Integer, ForeignKey("job_posts.id", ondelete="CASCADE"), nullable=False)
    similarity = Column(VARCHAR, nullable=False)  # 유사도,적합도 (예: 56)

    user = relationship("User", back_populates="user_similarities")      
    job_post = relationship("JobPost", back_populates="user_similarities")  