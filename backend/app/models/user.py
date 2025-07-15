from sqlalchemy import Column, Integer, String, DateTime, Date, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.PostgreSQL import Base
from app.models.user_experience import UserExperience
from app.models.user_certificate import UserCertificate
from app.models.user_preference import UserPreference
from app.models.user_roadmap import UserRoadmap

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)               # 이메일
    hashed_password = Column(String, nullable=True)                   # 비밀번호 해시 (소셜 로그인 시 null 가능)
    nickname = Column(String, unique=True, nullable=False)            # 닉네임
    signup_type = Column(String, nullable=False)                      # 가입 유형 ("id" or "naver")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # 가입일 (DEFAULT now)
    name = Column(String, nullable=False)                             # 이름
    phone_number = Column(String, nullable=False)                     # 연락처
    birth_date = Column(Date, nullable=False)                         # 생년월일
    gender = Column(String, nullable=False)                           # 성별
    university = Column(String, nullable=True)                        # 대학교 (optional)
    major = Column(String, nullable=True)                             # 전공/학과 (optional)
    gpa = Column(Float, nullable=True)                                # 학점 (optional)
    education_status = Column(String, nullable=True)                  # 학력 상태 (재학/졸업/휴학/졸업예정 등)
    degree = Column(String, nullable=False,default="고등학교")                           # 학위
    language_score = Column(JSON, nullable=True, default=dict)       # 어학 점수 (JSON, ex: {"TOEIC": 500})
    desired_job = Column(String, nullable=True)                       # 희망 직무 (optional)
    working_year = Column(String, nullable=False, default="신입")      # 연차 ("신입" or "경력 N년차")
    todo_list = Column(JSON, nullable=True, default=list)             # 투두리스트 (JSON list)

    # Relationships to other tables (one-to-many)
    experiences = relationship("UserExperience", back_populates="user", cascade="all, delete-orphan")
    user_skills = relationship("UserSkill", back_populates="user", cascade="all, delete-orphan")
    user_certificates = relationship("UserCertificate", back_populates="user", cascade="all, delete-orphan")
    user_preferences = relationship("UserPreference", back_populates="user", cascade="all, delete-orphan")
    user_roadmaps = relationship("UserRoadmap", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
User.user_similarities = relationship("UserSimilarity", back_populates="user", cascade="all, delete-orphan")
