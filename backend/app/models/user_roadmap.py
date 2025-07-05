from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database.PostgreSQL import Base

class UserRoadmap(Base):
    __tablename__ = "user_roadmaps"
    __table_args__ = (UniqueConstraint("user_id", "roadmaps_id", name="uix_user_roadmap"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    roadmaps_id = Column(Integer, ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False)

    user = relationship("User", back_populates="user_roadmaps")
    roadmap = relationship("Roadmap", back_populates="users")
