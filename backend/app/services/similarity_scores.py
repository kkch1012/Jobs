import os
import json
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.job_postings import JobPosting
from app.models.user_similarity import UserSimilarity

# Step 1. 환경 변수 로드
load_dotenv()

# Step 3. 유저 데이터 로드
def load_user_data(user_id: int, engine) -> dict:
    query = f"""
    SELECT 
        u.id, u.name, u.gender, u.university, u.major, u.education_status, u.degree,
        u.language_score, u.desired_job,
        ue.name AS experience_name, ue.period AS experience_period, ue.description AS experience_description,
        s.name AS skill_name, us.proficiency AS skill_proficiency,
        c.name AS certificate_name
    FROM "Users" u
    LEFT JOIN "UserExperience" ue ON u.experience_id = ue.id
    LEFT JOIN "User_Skill" us ON u.id = us.user_id
    LEFT JOIN "Skill" s ON us.skill_id = s.id
    LEFT JOIN "User_Certificate" uc ON uc.user_id = u.id
    LEFT JOIN "Certificate" c ON uc.certificate_id = c.id
    WHERE u.id = {user_id}
    """
    df = pd.read_sql(query, engine)
    user_base = df.iloc[0][[
        "id", "name", "gender", "university", "major", "education_status",
        "degree", "language_score", "desired_job"
    ]].to_dict()
    try:
        user_base["language_score"] = json.loads(user_base["language_score"])
    except:
        user_base["language_score"] = {}

    experience = {
        "name": df.iloc[0]["experience_name"],
        "period": df.iloc[0]["experience_period"],
        "description": df.iloc[0]["experience_description"]
    }

    skills_df = df[["skill_name", "skill_proficiency"]].dropna().drop_duplicates()
    skill_names = skills_df["skill_name"].tolist()
    proficiencies = skills_df["skill_proficiency"].tolist()
    certificates = df["certificate_name"].dropna().drop_duplicates().tolist()

    return {
        **user_base,
        "experience": [experience],
        "skill_id": skill_names,
        "proficiency": proficiencies,
        "certificate_id": certificates
    }

# Step 4. 공고 데이터 로드
def load_job_data(engine):
    query = "SELECT id, full_embedding FROM job_postings"
    return pd.read_sql(query, engine)

# Step 5. 유저 임베딩 생성
embedder = SentenceTransformer("intfloat/multilingual-e5-large")

def summarize_user_for_embedding(user: User) -> str:
    # ORM 객체에서 정보 추출
    skills = [f"{s.skill.name}({s.proficiency})" for s in user.skills]
    certs = [c.certificate.name for c in user.certificates]
    exp = user.experience
    exp_text = f"{exp.name}, {exp.period}, {exp.description}" if exp else "없음"
    return (
        f"이름: {user.name}\n"
        f"성별: {user.gender}, 학교: {user.university}, 학과: {user.major}, "
        f"학위: {user.degree}, 학력 상태: {user.education_status}\n"
        f"희망 직무: {user.desired_job}\n"
        f"어학 점수: {user.language_score}\n"
        f"기술 스택: {', '.join(skills) or '없음'}\n"
        f"자격증: {', '.join(certs) or '없음'}\n"
        f"경험: {exp_text}"
    )

def get_user_embedding(user: User) -> np.ndarray:
    user_text = summarize_user_for_embedding(user)
    embedding = embedder.encode(user_text, normalize_embeddings=True)
    return np.array(embedding)

def compute_similarity_scores(user: User, db: Session):
    user_embedding = get_user_embedding(user)
    jobs = db.query(JobPosting).all()
    job_embeddings = np.vstack([np.array(j.full_embedding) for j in jobs])
    similarity_scores = cosine_similarity([user_embedding], job_embeddings)[0]
    return [(jobs[i].id, float(similarity_scores[i])) for i in range(len(jobs))]

def save_similarity_scores(user: User, scores, db: Session):
    for job_id, sim in scores:
        db.add(UserSimilarity(user_id=user.id, job_post_id=job_id, similarity=sim))
    db.commit()
