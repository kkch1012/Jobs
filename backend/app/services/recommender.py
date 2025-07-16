'''
추천 로직 파일
'''

import numpy as np
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.job_post import JobPost
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Any, Tuple
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
    skills = [f"{s.skill.name}({s.proficiency})" for s in user.user_skills]
    skill_part = ", ".join(skills) if skills else "없음"
    cert_part = ", ".join([c.certificate.name for c in user.user_certificates]) or "없음"
    exp = user.experiences[0] if user.experiences else None
    exp_text = f"{exp.name}, {exp.period}, {exp.description}" if exp else "없음"
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

# === ★ 수정된 부분: 유사도 점수를 반환하지 않고 채용 공고 객체 리스트만 반환 ===
def get_top_n_jobs(user_embedding: np.ndarray, jobs: List[JobPost], n: int = 20) -> List[JobPost]:
    """
    사용자 임베딩과 가장 유사한 상위 N개의 채용 공고 리스트를 반환합니다.
    """
    valid_jobs = [j for j in jobs if hasattr(j, 'full_embedding') and j.full_embedding is not None]
    if not valid_jobs:
        return []
    
    job_embeddings = np.vstack([
        np.array(j.full_embedding) if not isinstance(j.full_embedding, np.ndarray) else j.full_embedding
        for j in valid_jobs
    ])
    
    sims = cosine_similarity([user_embedding], job_embeddings)[0]
    jobs_with_sim = list(zip(valid_jobs, sims))
    jobs_with_sim.sort(key=lambda x: x[1], reverse=True)
    
    # 유사도 점수는 정렬에만 사용하고, 최종적으로는 JobPost 객체만 반환합니다.
    return [job for job, _ in jobs_with_sim[:n]]

def summarize_user_text(user: User) -> str:
    return summarize_user_for_embedding(user)

def make_prompt(user_summary: str, job_list: List[JobPost]) -> str:
    # 이 함수의 내용은 변경되지 않았습니다.
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

def call_qwen_api(prompt: str, api_key: str) -> str | None:
    # 이 함수의 내용은 변경되지 않았습니다.
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": "Job Recommender"
    }
    body = {
        "model": "qwen/qwen-turbo:free",
        "messages": [
            {"role": "system", "content": "너는 한국 채용 시장에 대해 잘 아는 최고의 채용 공고 추천 전문가야. 사용자에게 친근하고 명확한 어조로 설명해줘."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 4096
    }

    try:
        response = requests.post(url, headers=headers, json=body, timeout=60)
        response.raise_for_status()
        
        response_json = response.json()
        
        choice = response_json.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        return content if content else None

    except requests.exceptions.RequestException as e:
        print(f"API 요청 실패: 네트워크 또는 서버 오류. Error: {e}")
        return None
    except (KeyError, IndexError) as e:
        print(f"API 응답 파싱 실패: 예상치 못한 JSON 구조. Error: {e}")
        return None
    except Exception as e:
        print(f"API 호출 중 예상치 못한 오류 발생: {e}")
        return None

# === ★ 수정된 부분: 대체 응답 메시지에서 유사도 점수 표시 제거 ===
def recommend_jobs_for_user(user_id: int, db: Session, api_key: str, top_n: int = 30) -> str:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    jobs = db.query(JobPost).all()
    if not jobs:
        return "현재 추천할 수 있는 채용 공고가 없습니다."

    user_embedding = get_user_embedding(user)
    
    # 유사도 순으로 정렬된 공고 리스트 가져오기
    top_jobs = get_top_n_jobs(user_embedding, jobs, n=top_n)

    if not top_jobs:
        return "회원님과 유사한 채용 공고를 찾지 못했습니다."

    user_summary = summarize_user_text(user)
    prompt = make_prompt(user_summary, top_jobs)
    
    # LLM API 호출
    llm_recommendation = call_qwen_api(prompt, api_key)

    if llm_recommendation:
        print("LLM 추천 생성 성공")
        return ll_recommendation
    else:
        print("LLM 추천 생성 실패. 대체 응답을 생성합니다.")
        fallback_message = (
            "🤖 AI 추천을 생성하는 중 오류가 발생했습니다.\n"
            "대신 회원님의 이력서와 가장 유사도가 높은 공고를 순서대로 보여드릴게요!\n\n"
            "--- 유사도 순 추천 목록 ---\n"
        )
        # 유사도 점수를 제외하고 회사명과 직무명만 표시합니다.
        for job in top_jobs[:5]:
             fallback_message += f"✅ **{job.company_name} - {job.title}**\n"

        return fallback_message
