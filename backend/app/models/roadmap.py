from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.PostgreSQL import Base

class Roadmap(Base):
    __tablename__ = "roadmaps"

    id = Column(Integer, primary_key=True, index=True)               # 로드맵 ID
    name = Column(String, nullable=False)                            # 컨텐츠 이름
    type = Column(String, nullable=False)                            # ex) 부트캠프, 코스
    description = Column(Text, nullable=False)                       # 컨텐츠 설명
    start_date = Column(DateTime, nullable=False)                    # 시작일
    end_date = Column(DateTime, nullable=False)                      # 마감일
    status = Column(String, nullable=False)                          # 상태 (예: 진행 중, 완료 등)

    # 관계 (유저와의 연결은 중간 테이블 UserRoadmap으로 연결)
    users = relationship("UserRoadmap", back_populates="roadmap", cascade="all, delete-orphan")