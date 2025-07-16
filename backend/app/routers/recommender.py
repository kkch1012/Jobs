from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.services.recommender import recommend_jobs_for_user, get_top_n_jobs, make_prompt, call_qwen_api
from app.services.similarity_scores import get_user_embedding
from app.utils.dependencies import get_current_user
import os
import re
import json

router = APIRouter(prefix="/recommend", tags=["Recommend"])

@router.get(
    "/jobs",
    summary="맞춤형 채용공고 추천",
    description="""
현재 로그인된 사용자에게 맞춤형 채용공고를 추천합니다.

- **유사도 계산**: 사용자의 프로필(기술, 경험 등)과 각 채용공고의 임베딩 값을 비교하여 유사도를 계산합니다.
- **LLM 재추천**: 유사도 상위 20개의 공고를 LLM(Qwen)에게 보내, 최종적으로 가장 적합한 5개의 공고와 그 이유를 추천받습니다.
- **API 키 필요**: 이 기능을 사용하려면 서버 환경변수에 `OPENROUTER_API_KEY`가 설정되어 있어야 합니다.
- **권한**: 로그인된 사용자만 사용 가능
"""
)
def recommend_for_current_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, 
            detail="OPENROUTER_API_KEY 환경변수가 설정되어 있지 않습니다."
        )
    
    try:
        result = recommend_jobs_for_user(current_user, db, api_key, 20)
        return {"recommendation": result}
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"추천 생성 중 오류가 발생했습니다: {str(e)}"
        )

@router.get(
    "/jobs/ids",
    summary="추천 채용공고 상세 목록",
    description="""
현재 로그인된 사용자에게 추천할 채용공고의 상세 정보를 반환합니다.

- **유사도 기반**: 사용자와 유사도가 높은 상위 20개 공고에서 선별
- **LLM 선별**: LLM이 20개 중에서 가장 적합한 5개를 선별
- **응답**: 채용공고 상세 정보와 함께 반환 (user_preference와 유사한 형태)
"""
)
def get_recommended_job_ids(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, 
            detail="OPENROUTER_API_KEY 환경변수가 설정되어 있지 않습니다."
        )
    
    try:
        from app.models.job_post import JobPost
        from app.schemas.job_post import JobPostResponse
        
        jobs = db.query(JobPost).all()
        if not jobs:
            return {"recommended_jobs": [], "message": "현재 추천할 수 있는 채용 공고가 없습니다."}

        user_embedding = get_user_embedding(current_user)
        top_jobs = get_top_n_jobs(user_embedding, jobs, n=20)

        if not top_jobs:
            return {"recommended_jobs": [], "message": "회원님과 유사한 채용공고를 찾지 못했습니다."}

        # ID 추출 전용 프롬프트 생성
        job_ids_text = "\n".join([f"공고 ID: {job.id}" for job in top_jobs])  # 20개 전송
        
        id_extraction_prompt = f"""
다음은 사용자와 유사도가 높은 채용공고 20개입니다.

{job_ids_text}

위 공고 중에서 사용자에게 가장 적합한 5개의 공고 ID만 추출해주세요.
응답은 반드시 다음과 같은 JSON 형태로만 해주세요:

{{
  "recommended_job_ids": [123, 456, 789, 101, 112]
}}

설명이나 다른 텍스트는 포함하지 말고 JSON만 반환해주세요.
"""

        # LLM API 호출
        llm_response = call_qwen_api(id_extraction_prompt, api_key)
        
        recommended_job_ids = []
        if llm_response:
            # JSON 파싱 시도
            try:
                # JSON 부분만 추출
                json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    result = json.loads(json_str)
                    recommended_job_ids = result.get("recommended_job_ids", [])
                else:
                    raise ValueError("JSON 형식을 찾을 수 없습니다.")
            except Exception as e:
                print(f"JSON 파싱 실패: {e}")
                # 파싱 실패 시 상위 5개 ID 반환
                recommended_job_ids = [job.id for job in top_jobs[:5]]
        else:
            # LLM 실패 시 상위 5개 ID 반환
            recommended_job_ids = [job.id for job in top_jobs[:5]]
        
        # 추천된 ID에 해당하는 채용공고 상세 정보 조회 (유사도 포함)
        from app.models.user_similarity import UserSimilarity
        from sqlalchemy import and_, null
        
        job_responses = []
        for job_id in recommended_job_ids:
            # 유사도 점수와 함께 조회
            result = db.query(JobPost, UserSimilarity.similarity).outerjoin(
                UserSimilarity,
                and_(
                    JobPost.id == UserSimilarity.job_post_id,
                    UserSimilarity.user_id == current_user.id
                )
            ).filter(JobPost.id == job_id).first()
            
            if result:
                job, similarity = result
                job_response = JobPostResponse.model_validate(job)
                job_response.similarity = similarity
                job_responses.append(job_response)
        
        return {
            "recommended_jobs": job_responses,
            "total_candidates": len(top_jobs),
            "recommended_count": len(job_responses)
        }
            
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"추천 채용공고 상세 정보 조회 중 오류가 발생했습니다: {str(e)}"
        )



@router.post(
    "/jobs/explanation",
    summary="추천 채용공고 설명 생성",
    description="""
특정 채용공고 ID들에 대한 추천 이유와 설명을 생성합니다.

- **입력**: 채용공고 ID 리스트
- **출력**: 각 공고별 상세한 추천 이유와 설명
"""
)
def generate_job_explanations(
    job_ids: list[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, 
            detail="OPENROUTER_API_KEY 환경변수가 설정되어 있지 않습니다."
        )
    
    try:
        from app.models.job_post import JobPost
        
        # 채용공고 조회
        jobs = db.query(JobPost).filter(JobPost.id.in_(job_ids)).all()
        if not jobs:
            return {"explanations": [], "message": "해당 ID의 채용공고를 찾을 수 없습니다."}

        # 사용자 정보 요약
        from app.services.similarity_scores import summarize_user_for_embedding
        user_summary = summarize_user_for_embedding(current_user)
        
        # 설명 생성용 프롬프트
        job_details = []
        for job in jobs:
            job_detail = (
                f"공고 ID: {job.id}\n"
                f"직무명: {job.title}\n"
                f"회사명: {job.company_name}\n"
                f"주요 업무: {job.main_tasks or '없음'}\n"
                f"자격 요건: {job.qualifications or '없음'}\n"
                f"우대 사항: {job.preferences or '없음'}\n"
                f"기술 스택: {job.tech_stack or '없음'}"
            )
            job_details.append(job_detail)
        
        jobs_text = "\n---\n".join(job_details)
        
        explanation_prompt = f"""
다음은 사용자 정보와 추천된 채용공고들입니다.

[사용자 정보]
{user_summary}

[추천된 채용공고]
{jobs_text}

각 채용공고에 대해 다음을 설명해주세요:
1. 이 공고가 사용자에게 적합한 이유
2. 사용자의 어떤 경험이나 기술이 이 공고와 매칭되는지
3. 지원 시 주의할 점이나 준비사항

각 공고별로 명확하게 구분하여 설명해주세요.
"""

        # LLM API 호출
        llm_explanation = call_qwen_api(explanation_prompt, api_key)
        
        if llm_explanation:
            return {
                "explanations": llm_explanation,
                "job_count": len(jobs),
                "user_id": current_user.id
            }
        else:
            return {
                "explanations": "설명 생성에 실패했습니다.",
                "job_count": len(jobs),
                "user_id": current_user.id
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"설명 생성 중 오류가 발생했습니다: {str(e)}"
        )

@router.get(
    "/jobs/{user_id}",
    summary="특정 사용자 맞춤형 채용공고 추천 (관리자용)",
    description="""
특정 사용자 ID에 대한 맞춤형 채용공고를 추천합니다.

- **권한**: 관리자만 사용 가능
- **주의**: 일반적으로는 `/recommend/jobs`를 사용하세요
"""
)
def recommend_for_specific_user(
    user_id: int,
    top_n: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 관리자 권한 확인 (예: admin 필드가 있다면)
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="관리자만 사용할 수 있습니다.")
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, 
            detail="OPENROUTER_API_KEY 환경변수가 설정되어 있지 않습니다."
        )
    
    # 사용자 존재 확인
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    
    try:
        result = recommend_jobs_for_user(user, db, api_key, top_n)
        return {"recommendation": result}
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"추천 생성 중 오류가 발생했습니다: {str(e)}"
        )