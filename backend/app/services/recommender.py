from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from app.models.user import User
from app.models.job_post import JobPost
from app.models.user_similarity import UserSimilarity
from app.services.similarity_scores import (
    summarize_user_for_embedding,
    auto_compute_user_similarity
)
from typing import List
import os
import requests
from app.utils.logger import recommender_logger

def get_top_n_jobs_with_scores(user: User, db: Session, n: int = 20) -> List[tuple[JobPost, float]]:
    """
    사용자와 가장 유사한 상위 N개의 채용 공고와 유사도 점수를 반환합니다.
    UserSimilarity 테이블에서 미리 계산된 유사도를 사용합니다.
    """
    try:
        # UserSimilarity 테이블에서 상위 N개 유사도 조회
        top_similarities = db.query(UserSimilarity, JobPost).join(
            JobPost, UserSimilarity.job_post_id == JobPost.id
        ).filter(
            UserSimilarity.user_id == user.id
        ).order_by(
            desc(UserSimilarity.similarity)
        ).limit(n).all()
        
        if not top_similarities:
            # 유사도가 없으면 자동 계산 시도
            recommender_logger.info(f"사용자 {user.id}의 유사도 데이터가 없어 자동 계산을 시도합니다.")
            job_posts = db.query(JobPost).filter(JobPost.full_embedding.isnot(None)).all()
            if job_posts:
                auto_compute_user_similarity(user, db, job_posts)
                # 다시 조회
                top_similarities = db.query(UserSimilarity, JobPost).join(
                    JobPost, UserSimilarity.job_post_id == JobPost.id
                ).filter(
                    UserSimilarity.user_id == user.id
                ).order_by(
                    desc(UserSimilarity.similarity)
                ).limit(n).all()
        
        # 결과 반환
        result = []
        for similarity, job in top_similarities:
            result.append((job, similarity.similarity))
        
        return result
        
    except Exception as e:
        recommender_logger.error(f"유사도 조회 중 오류 발생: {str(e)}")
        return []

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
        "- 최적의 공고 5개를 추천해주세요\n"
        "- 마크다운 형식(**, ### 등)을 사용하지 말고 일반 텍스트로 작성해주세요\n"
        "- 각 공고별로 명확하게 구분하여 설명해주세요\n"
        "- 줄바꿈을 적절히 사용하여 읽기 쉽게 작성해주세요\n\n"
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
    
    # 더 안정적인 모델 사용
    model = "qwen/qwen3-30b-a3b"
    
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "너는 한국 채용 시장에 대해 잘 아는 최고의 채용 공고 추천 전문가야. 사용자에게 친근하고 명확한 어조로 설명해줘."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 4096
    }

    try:
        recommender_logger.info(f"OpenRouter API 호출 시작: {url}")
        recommender_logger.info(f"API 키 확인: {api_key[:10]}...")
        
        response = requests.post(url, headers=headers, json=body, timeout=60)
        
        recommender_logger.info(f"API 응답 상태 코드: {response.status_code}")
        
        if response.status_code != 200:
            recommender_logger.error(f"API 응답 오류: {response.status_code} - {response.text}")
            return None
            
        response.raise_for_status()
        
        response_json = response.json()
        recommender_logger.info(f"API 응답 구조: {list(response_json.keys())}")
        
        choice = response_json.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        if content:
            recommender_logger.info("API 응답에서 content 추출 성공")
            return content
        else:
            recommender_logger.error("API 응답에서 content가 비어있음")
            return None

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
    # 유사도 순으로 정렬된 공고 리스트 가져오기 (유사도 점수 포함)
    top_jobs_with_sim = get_top_n_jobs_with_scores(user, db, n=top_n)

    if not top_jobs_with_sim:
        return "회원님과 유사한 채용 공고를 찾지 못했습니다."

    # JobPost 객체만 추출
    top_jobs = [job for job, _ in top_jobs_with_sim]

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
        # 유사도 점수와 함께 회사명과 직무명을 표시합니다.
        for job, similarity in top_jobs_with_sim[:5]:
             fallback_message += f"✅ **{job.company_name} - {job.title}** (적합도: {similarity:.2f})\n"

        return fallback_message
