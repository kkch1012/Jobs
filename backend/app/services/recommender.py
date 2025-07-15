'''
추천 로직 파일
'''

import numpy as np
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.job_post import JobPost
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Any
import os
import requests

# 임베딩 모델 싱글턴
_embedder = None
def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("intfloat/multilingual-e5-large")
    return _embedder

def summarize_user_for_embedding(user: User) -> str:
    # ORM User 객체에서 필요한 정보 추출
    skills = [f"{s.skill.name}({s.proficiency})" for s in user.user_skills]
    skill_part = ", ".join(skills) if skills else "없음"
    cert_part = ", ".join([c.certificate.name for c in user.user_certificates]) or "없음"
    exp = user.experiences[0] if user.experiences else None
    exp_text = f"{exp.name}, {exp.period}, {exp.description}" if exp else "없음"
    # language_score는 dict 또는 None일 수 있음
    lang_score = '없음'
    if getattr(user, 'language_score', None) is not None and isinstance(user.language_score, dict):
        lang_score = user.language_score.get('OPIC', '없음')
    return (
        f"이름: {user.name}\n"
        f"성별: {user.gender}, 학교: {user.university}, 학과: {user.major}, "
        f"학위: {user.degree}, 학력 상태: {user.education_status}\n"
        f"희망 직무: {user.desired_job}\n"
        f"어학 점수: {lang_score}\n"
        f"기술 스택: {skill_part}\n"
        f"자격증: {cert_part}\n"
        f"경험: {exp_text}"
    )

def get_user_embedding(user: User) -> np.ndarray:
    user_text = summarize_user_for_embedding(user)
    embedder = get_embedder()
    embedding = embedder.encode(user_text, normalize_embeddings=True)
    return np.array(embedding)

def get_top_n_jobs(user_embedding: np.ndarray, jobs: List[JobPost], n: int = 20) -> List[JobPost]:
    # Only use jobs with a valid full_embedding (not None and is a numpy array or list)
    valid_jobs = [j for j in jobs if hasattr(j, 'full_embedding') and j.full_embedding is not None]
    # Convert SQLAlchemy Vector to numpy array if needed
    job_embeddings = np.vstack([
        np.array(j.full_embedding) if not isinstance(j.full_embedding, np.ndarray) else j.full_embedding
        for j in valid_jobs
    ])
    sims = cosine_similarity([user_embedding], job_embeddings)[0]
    jobs_with_sim = list(zip(valid_jobs, sims))
    jobs_with_sim.sort(key=lambda x: x[1], reverse=True)
    return [job for job, _ in jobs_with_sim[:n]]

def summarize_user_text(user: User) -> str:
    # 위와 동일, 혹은 별도 포맷
    return summarize_user_for_embedding(user)

def make_prompt(user_summary: str, job_list: List[JobPost]) -> str:
    job_str_list = [
        f"공고 ID: {job.id}\n"
        f"직무명: {job.title}\n"
        f"주요 업무: {job.main_tasks}\n"
        f"자격 요건: {job.qualifications}\n"
        f"우대 사항: {job.preferences}\n"
        f"기술 스택: {job.tech_stack}"
        for job in job_list
    ]
    jobs_text = "\n---\n".join(job_str_list)
    return (
        "다음은 신입 데이터 분석가의 상세 이력과 채용 공고 20개입니다.\n\n"
        "[지원자 정보]\n" + user_summary + "\n\n"
        "[요청사항]\n"
        "- 아래 공고 중 현실적으로 맞지 않는 조건(병역특례, 경력 등)은 제외\n"
        "- 숙련도 기준 가중치 반영 (상=3, 중=2, 하=1)\n"
        "- 최적의 공고 5개를 아래 양식으로 출력\n\n"
        "[채용 공고 목록]\n" + jobs_text
    )

def call_qwen_api(prompt: str, api_key: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": "Job Recommender"
    }
    body = {
        "model": "qwen/qwen3-32b:free",
        "messages": [
            {"role": "system", "content": "너는 채용 공고 추천 전문가야."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 4096
    }
    response = requests.post(url, headers=headers, json=body)
    response.raise_for_status()
    print("LLM raw response:", response.json())  # ★ 추가
    # 기존 코드
    response_json = response.json()
    print("LLM raw response:", response_json)
    msg = response_json["choices"][0]["message"]
    content = msg.get("content", "")
    if not content and "reasoning" in msg:
        content = msg["reasoning"]
    return content

def recommend_jobs_for_user(user_id: int, db: Session, api_key: str, top_n: int = 30) -> str:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")
    print("user:", user)

    jobs = db.query(JobPost).all()
    print("jobs count:", len(jobs))

    user_embedding = get_user_embedding(user)
    print("user_embedding shape:", user_embedding.shape)

    top_jobs = get_top_n_jobs(user_embedding, jobs, n=top_n)
    print("top_jobs count:", len(top_jobs))

    user_summary = summarize_user_text(user)
    print("user_summary:", user_summary)

    prompt = make_prompt(user_summary, top_jobs)
    print("prompt:", prompt)

    result = call_qwen_api(prompt, api_key)
    print("llm result:", result)
    return result