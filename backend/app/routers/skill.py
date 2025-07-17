from fastapi import APIRouter, Depends, HTTPException, Response, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.skill import Skill
from app.schemas.skill import SkillCreate, SkillResponse
from app.utils.dependencies import get_current_user
from app.utils.logger import app_logger
from typing import List, Optional
from app.models.user import User
from sqlalchemy import or_

router = APIRouter(prefix="/skills", tags=["skills"])

@router.get(
    "/",
    response_model=List[SkillResponse],
    summary="전체 기술 스택 조회",
    description="등록된 모든 기술 스택을 조회합니다."
)
def list_all_skills(
    db: Session = Depends(get_db)
):
    try:
        skills = db.query(Skill).all()
        app_logger.info(f"기술 스택 조회 완료: {len(skills)}건")
        return skills
    except Exception as e:
        app_logger.error(f"기술 스택 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"기술 스택 조회 중 오류가 발생했습니다: {str(e)}")

@router.get(
    "/search",
    response_model=List[SkillResponse],
    summary="기술 스택 검색",
    description="기술 스택을 검색합니다. 부분 문자열 검색을 지원합니다."
)
def search_skills(
    query: str = Query(..., description="검색할 기술명"),
    limit: int = Query(10, ge=1, le=50, description="최대 반환 개수"),
    exact_match: bool = Query(False, description="정확한 일치만 검색"),
    db: Session = Depends(get_db)
):
    try:
        if not query.strip():
            return []
        
        # 검색 쿼리 구성
        if exact_match:
            # 정확한 일치 검색
            skills = db.query(Skill).filter(Skill.name == query.strip()).limit(limit).all()
        else:
            # 부분 문자열 검색 (대소문자 구분 없음)
            search_term = f"%{query.strip()}%"
            skills = db.query(Skill).filter(
                or_(
                    Skill.name.ilike(search_term),
                    Skill.name.ilike(f"%{query.strip().lower()}%"),
                    Skill.name.ilike(f"%{query.strip().upper()}%")
                )
            ).limit(limit).all()
        
        app_logger.info(f"기술 스택 검색 완료: {query} → {len(skills)}건")
        return skills
        
    except Exception as e:
        app_logger.error(f"기술 스택 검색 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"기술 스택 검색 중 오류가 발생했습니다: {str(e)}")

@router.post(
    "/",
    response_model=SkillResponse,
    summary="새로운 기술 스택 등록",
    description="새로운 기술 스택을 등록합니다."
)
def create_skill(
    skill: SkillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # 중복 체크
        existing_skill = db.query(Skill).filter(Skill.name == skill.name).first()
        if existing_skill:
            raise HTTPException(status_code=400, detail="이미 등록된 기술명입니다.")
        
        db_skill = Skill(**skill.dict())
        db.add(db_skill)
        db.commit()
        db.refresh(db_skill)
        
        app_logger.info(f"새로운 기술 스택 등록 완료: {db_skill.name}")
        return db_skill
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"기술 스택 등록 실패: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"기술 스택 등록 중 오류가 발생했습니다: {str(e)}")

@router.delete(
    "/{skill_id}",
    summary="기술 스택 삭제",
    description="기존 기술 스택을 삭제합니다."
)
def delete_skill(
    skill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        skill = db.query(Skill).filter(Skill.id == skill_id).first()
        if not skill:
            raise HTTPException(status_code=404, detail="해당 기술 항목을 찾을 수 없습니다.")
        
        db.delete(skill)
        db.commit()
        
        app_logger.info(f"기술 스택 삭제 완료: {skill.name}")
        return {"message": "기술 스택이 성공적으로 삭제되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"기술 스택 삭제 실패: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"기술 스택 삭제 중 오류가 발생했습니다: {str(e)}")