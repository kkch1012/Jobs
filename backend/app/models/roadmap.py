from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.PostgreSQL import Base

class Roadmap(Base):
    __tablename__ = "roadmaps"

    id = Column(Integer, primary_key=True, index=True)               # 로드맵 ID
    name = Column(String, nullable=False)                            # 컨텐츠 이름
    type = Column(String, nullable=False)                            # ex) 부트캠프, 코스
    skill_description = Column(JSON, nullable=False)                 # 컨텐츠 설명
    start_date = Column(DateTime, nullable=True)                    # 시작일
    end_date = Column(DateTime, nullable=True)                      # 마감일
    status = Column(String, nullable=True)                          # 상태 (예: 진행 중, 완료 등)
    deadline = Column(DateTime, nullable=True)                       # 마감일(선택, null 허용)
    location = Column(String, nullable=True)                         # 장소
    onoff = Column(String, nullable=True)                            # 온/오프/온오프 (on, off, onoff)
    participation_time = Column(String, nullable=True)               # 참여 시간
    company = Column(String, nullable=True)                          # 회사명
    program_course = Column(String, nullable=True)                   # 프로그램/코스명
    price = Column(String, nullable=True)                            # 가격
    url = Column(String, nullable=True, unique=True)                 # 링크 (UNIQUE)
    # 관계 (유저와의 연결은 중간 테이블 UserRoadmap으로 연결)
    users = relationship("UserRoadmap", back_populates="roadmap", cascade="all, delete-orphan")