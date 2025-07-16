import numpy as np
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.job_post import JobPost
from app.services.similarity_scores import get_user_embedding, summarize_user_for_embedding
from sklearn.metrics.pairwise import cosine_similarity
from typing import List
import os
import requests
from app.utils.logger import recommender_logger

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

def make_prompt(user_summary: str, job_list: List[JobPost]) -> str:
    """LLM 추천을 위한 프롬프트 생성"""
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
    """Qwen API를 호출하여 추천 결과 생성"""
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
        recommender_logger.error(f"API 요청 실패: 네트워크 또는 서버 오류. Error: {e}")
        return None
    except (KeyError, IndexError) as e:
        recommender_logger.error(f"API 응답 파싱 실패: 예상치 못한 JSON 구조. Error: {e}")
        return None
    except Exception as e:
        recommender_logger.error(f"API 호출 중 예상치 못한 오류 발생: {e}")
        return None

def recommend_jobs_for_user(user: User, db: Session, api_key: str, top_n: int = 30) -> str:
    """
    사용자에게 맞춤형 채용공고를 추천합니다.
    
    Args:
        user: 추천 대상 사용자
        db: 데이터베이스 세션
        api_key: OpenRouter API 키
        top_n: 유사도 상위 N개 공고에서 추천 (기본값: 30)
    
    Returns:
        추천 결과 문자열
    """
    jobs = db.query(JobPost).all()
    if not jobs:
        return "현재 추천할 수 있는 채용 공고가 없습니다."

    user_embedding = get_user_embedding(user)
    
    # 유사도 순으로 정렬된 공고 리스트 가져오기
    top_jobs = get_top_n_jobs(user_embedding, jobs, n=top_n)

    if not top_jobs:
        return "회원님과 유사한 채용 공고를 찾지 못했습니다."

    user_summary = summarize_user_for_embedding(user)
    prompt = make_prompt(user_summary, top_jobs)
    
    # LLM API 호출
    llm_recommendation = call_qwen_api(prompt, api_key)

    if llm_recommendation:
        recommender_logger.info("LLM 추천 생성 성공")
        return llm_recommendation
    else:
        recommender_logger.warning("LLM 추천 생성 실패. 대체 응답을 생성합니다.")
        fallback_message = (
            "🤖 AI 추천을 생성하는 중 오류가 발생했습니다.\n"
            "대신 회원님의 이력서와 가장 유사도가 높은 공고를 순서대로 보여드릴게요!\n\n"
            "--- 유사도 순 추천 목록 ---\n"
        )
        # 유사도 점수를 제외하고 회사명과 직무명만 표시합니다.
        for job in top_jobs[:5]:
             fallback_message += f"✅ **{job.company_name} - {job.title}**\n"

        return fallback_message
