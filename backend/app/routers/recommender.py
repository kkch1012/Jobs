from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.services.recommender import recommend_jobs_for_user, get_top_n_jobs_with_scores, make_prompt, call_qwen_api

from app.services.jobs_gap import recommend_job_for_user, get_job_recommendation_simple
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
        from app.schemas.job_post import JobPostSimpleResponse
        
        jobs = db.query(JobPost).all()
        if not jobs:
            return {"recommended_jobs": [], "message": "현재 추천할 수 있는 채용 공고가 없습니다."}

        top_jobs_with_sim = get_top_n_jobs_with_scores(current_user, jobs, n=20)

        if not top_jobs_with_sim:
            return {"recommended_jobs": [], "message": "회원님과 유사한 채용공고를 찾지 못했습니다."}

        # JobPost 객체만 추출
        top_jobs = [job for job, _ in top_jobs_with_sim]

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
                # 파싱 실패 시 상위 5개 ID 반환 (유사도 순)
                recommended_job_ids = [job.id for job, _ in top_jobs_with_sim[:5]]
        else:
            # LLM 실패 시 상위 5개 ID 반환 (유사도 순)
            recommended_job_ids = [job.id for job, _ in top_jobs_with_sim[:5]]
        
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
                job_response = JobPostSimpleResponse.model_validate(job)
                job_response.similarity = similarity
                job_responses.append(job_response)
        
        # 유사도 점수를 기준으로 내림차순 정렬 (높은 적합도 순)
        job_responses.sort(key=lambda x: x.similarity or 0, reverse=True)
        
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

주의사항:
- 마크다운 형식(**, ### 등)을 사용하지 말고 일반 텍스트로 작성해주세요
- 각 공고별로 명확하게 구분하여 설명해주세요
- 줄바꿈을 적절히 사용하여 읽기 쉽게 작성해주세요
- 번호나 기호를 사용하여 구조화해주세요
"""

        # LLM API 호출
        llm_explanation = call_qwen_api(explanation_prompt, api_key)
        
        if llm_explanation:
            return {
                "explanations": llm_explanation,
                "user_id": current_user.id
            }
        else:
            return {
                "explanations": "설명 생성에 실패했습니다.",
                "user_id": current_user.id
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"설명 생성 중 오류가 발생했습니다: {str(e)}"
        )

@router.get(
    "/jobs/paginated",
    summary="유사도 기반 채용공고 페이지별 조회",
    description="""
현재 로그인된 사용자와 유사도가 높은 채용공고를 페이지별로 조회합니다.

- **유사도 기반 정렬**: UserSimilarity 테이블의 유사도 점수를 기준으로 정렬
- **페이지별 조회**: 한 페이지당 지정된 개수의 채용공고를 유사도 높은 순으로 반환
- **페이징**: 프론트엔드에서 페이지 번호와 페이지당 개수를 지정하여 조회 가능
- **응답**: 채용공고 상세 정보와 유사도 점수, 전체 페이지 수 포함

**요청 파라미터:**
- `page`: 페이지 번호 (기본값: 1)
- `jobs_per_page`: 페이지당 공고 수 (기본값: 5, 최대: 50)

**응답 예시:**
```json
{
  "jobs": [
    {
      "id": 123,
      "title": "백엔드 개발자",
      "company_name": "테크컴퍼니",
      "similarity": 0.85,
      ...
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 10,
    "total_jobs": 50,
    "jobs_per_page": 5
  }
}
```
"""
)
def get_paginated_recommended_jobs(
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    jobs_per_page: int = Query(5, ge=1, le=50, description="페이지당 공고 수 (최대 50)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        from app.models.job_post import JobPost
        from app.models.user_similarity import UserSimilarity
        from app.schemas.job_post import JobPostSimpleResponse
        from sqlalchemy import and_, null
        
        # 유사도 점수와 함께 채용공고 조회 (유사도 높은 순으로 정렬)
        query = db.query(JobPost, UserSimilarity.similarity).join(
            UserSimilarity,
            and_(
                JobPost.id == UserSimilarity.job_post_id,
                UserSimilarity.user_id == current_user.id
            )
        ).order_by(UserSimilarity.similarity.desc())
        
        # 전체 개수 조회
        total_jobs = query.count()
        
        if total_jobs == 0:
            return {
                "jobs": [],
                "pagination": {
                    "current_page": page,
                    "total_pages": 0,
                    "total_jobs": 0,
                    "jobs_per_page": jobs_per_page
                },
                "message": "회원님과 유사한 채용공고를 찾지 못했습니다."
            }
        
        # 페이지네이션 계산
        total_pages = (total_jobs + jobs_per_page - 1) // jobs_per_page  # 올림 나눗셈
        
        # 페이지 번호 검증
        if page > total_pages:
            page = total_pages
        
        # 해당 페이지의 채용공고 조회
        offset = (page - 1) * jobs_per_page
        job_posts_with_similarity = query.offset(offset).limit(jobs_per_page).all()
        
        # 응답 데이터 구성
        job_responses = []
        for job, similarity in job_posts_with_similarity:
            job_response = JobPostSimpleResponse.model_validate(job)
            job_response.similarity = similarity
            job_responses.append(job_response)
        
        return {
            "jobs": job_responses,
            "pagination": {
                "current_page": page,
                "total_pages": total_pages,
                "total_jobs": total_jobs,
                "jobs_per_page": jobs_per_page
            }
        }
            
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"페이지별 추천 채용공고 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get(
    "/job",
    summary="직무 추천",
    description="""
현재 로그인된 사용자의 기술 스택을 분석하여 최적의 직무를 추천합니다.

- **기술 스택 분석**: 사용자가 등록한 기술과 숙련도를 분석
- **시장 트렌드 반영**: weekly_skill_stats 테이블의 데이터를 기반으로 시장 트렌드 반영
- **점수 계산**: 기술 매칭도와 숙련도 가중치를 고려한 점수 계산
- **응답**: 추천 직무명, 점수, 상세 분석 결과
"""
)
def recommend_job_for_current_user(
    verbose: bool = Query(False, description="상세 분석 결과 포함 여부"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        result = recommend_job_for_user(current_user, db, verbose=verbose)
        
        if result["recommended_job"] is None:
            return {
                "success": False,
                "message": result.get("message", "직무 추천에 실패했습니다."),
                "data": None
            }
        
        return {
            "success": True,
            "message": "직무 추천이 완료되었습니다.",
            "data": result
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"직무 추천 중 오류가 발생했습니다: {str(e)}"
        )


@router.get(
    "/job/simple",
    summary="간단한 직무 추천",
    description="""
현재 로그인된 사용자에게 추천 직무명만 반환합니다.

- **응답**: 추천 직무명 문자열만 반환
- **용도**: 간단한 직무 추천이 필요한 경우 사용
"""
)
def get_simple_job_recommendation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        recommended_job = get_job_recommendation_simple(current_user, db)
        
        return {
            "recommended_job": recommended_job,
            "user_id": current_user.id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"직무 추천 중 오류가 발생했습니다: {str(e)}"
        )