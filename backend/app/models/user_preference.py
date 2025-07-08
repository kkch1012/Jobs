from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database.PostgreSQL import Base
from app.models.job_post import JobPost
class UserPreference(Base):
    __tablename__ = "user_preferences"
    __table_args__ = (UniqueConstraint("user_id", "job_post_id", name="uix_user_job"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_post_id = Column(Integer, ForeignKey("job_posts.id", ondelete="CASCADE"), nullable=False)

    user = relationship("User", back_populates="user_preferences")
    job_posting = relationship("JobPost", back_populates="liked_by")
