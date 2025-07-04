from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.skill import Skill
from app.schemas.skill import SkillCreate, SkillResponse
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/skills", tags=["Skills"])

@router.get(
    "/",
    response_model=list[SkillResponse],
    summary="전체 기술 목록 조회",
    description="""
기술 DB에 등록된 전체 기술 목록을 조회합니다.

- 이 목록은 모든 사용자가 공통으로 사용할 수 있는 기술 목록입니다.
- 사용자 또는 관리자가 사용할 수 있으며 인증이 필요합니다.
"""
)
def list_skills(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    skills = db.query(Skill).filter(Skill.user_id == current_user.id).all()
    return skills


@router.post(
    "/",
    response_model=SkillResponse,
    summary="기술 항목 추가(관리자)",
    description="""
기술 마스터 DB에 새로운 기술 항목을 추가합니다.

- 이 API는 인증된 사용자(예: 관리자)가 기술 목록을 등록할 때 사용됩니다.
- 입력받은 기술명은 `Skill` 테이블에 저장됩니다.
"""
)
def add_skill(
    skill_data: SkillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_skill = Skill(user_id=current_user.id, name=skill_data.name)
    db.add(new_skill)
    db.commit()
    db.refresh(new_skill)
    return new_skill


@router.delete(
    "/{skill_id}",
    status_code=204,
    summary="기술 항목 삭제(관리자)",
    description="""
기술 마스터 DB에서 특정 기술 항목을 삭제합니다.

- `skill_id`는 삭제할 기술의 고유 ID입니다.
- 해당 기술이 존재하지 않거나, 본인이 등록한 항목이 아닌 경우 에러를 반환합니다.
- 관리자 또는 등록자가 삭제할 수 있습니다.
"""
)
def delete_skill(
    skill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="해당 기술 항목을 찾을 수 없습니다.")
    if skill.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="해당 기술 항목을 삭제할 권한이 없습니다.")
    db.delete(skill)
    db.commit()
    return Response(status_code=204)
