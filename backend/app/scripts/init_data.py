import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()
from app.database import SessionLocal
from app.models.skill import Skill
from app.models.certificate import Certificate
from app.models.roadmap import Roadmap
from app.models.job_post import JobPost         # 추가
from app.models.job_required_skill import JobRequiredSkill
from app.data.initial_data import (
    initial_skills,
    initial_certificates,
    initial_roadmaps,
    initial_job_posts,                         # 추가
)

def insert_skills(db: Session):
    for skill in initial_skills:
        exists = db.query(Skill).filter(Skill.name == skill["name"]).first()
        if not exists:
            db.add(Skill(name=skill["name"]))
    db.commit()
    print("초기 기술 목록 삽입 완료")

def insert_certificates(db: Session):
    for cert in initial_certificates:
        exists = db.query(Certificate).filter(Certificate.name == cert["name"]).first()
        if not exists:
            db.add(Certificate(name=cert["name"], issuer=cert["issuer"]))
    db.commit()
    print("초기 자격증 목록 삽입 완료")

def insert_roadmaps(db: Session):
    for roadmap in initial_roadmaps:
        exists = db.query(Roadmap).filter(Roadmap.name == roadmap["name"]).first()
        if not exists:
            db.add(
                Roadmap(
                    name=roadmap["name"],
                    type=roadmap["type"],
                    skill_description=roadmap["skill_description"],
                    start_date=roadmap["start_date"],
                    end_date=roadmap["end_date"],
                    status=roadmap["status"],
                )
            )
    db.commit()
    print("초기 로드맵 목록 삽입 완료")

def insert_job_posts(db: Session):
    for job_post in initial_job_posts:
        exists = db.query(JobPost).filter(JobPost.id == job_post["id"]).first()
        if not exists:
            db.add(JobPost(**job_post))
    db.commit()
    print("초기 채용공고 목록 삽입 완료")

def main():
    db = SessionLocal()
    try:
        insert_skills(db)
        insert_certificates(db)
        insert_roadmaps(db)
        insert_job_posts(db)
    finally:
        db.close()

if __name__ == "__main__":
    main()
