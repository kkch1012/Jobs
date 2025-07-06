from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user_skill import UserSkill
from app.schemas.user_skill import UserSkillCreate, UserSkillResponse
from app.utils.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/users/me/skills", tags=["UserSkill"])

from app.models.skill import Skill  # 스킬 테이블 모델 임포트

@router.post("/", response_model=UserSkillResponse, summary="보유 기술 추가", description="""
사용자의 이력서에 기술을 추가합니다.

- `skill_name`: 스킬 이름
- `proficiency`: 사용자의 숙련도 (예: 1~5)
- 인증된 사용자만 사용할 수 있습니다.
""")
def add_user_skill_by_name(
    skill_data: UserSkillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    skill = db.query(Skill).filter(Skill.name == skill_data.skill_name).first()
    if not skill:
        raise HTTPException(status_code=404, detail="스킬을 찾을 수 없습니다.")

    user_skill = UserSkill(
        user_id=current_user.id,
        skill_id=skill.id,
        proficiency=skill_data.proficiency
    )
    db.add(user_skill)
    db.commit()
    db.refresh(user_skill)
    return user_skill


@router.get("/", response_model=List[UserSkillResponse], summary="보유 기술 목록", description="""
로그인한 사용자가 등록한 기술 목록을 조회합니다.

- 인증된 사용자만 접근 가능
- 등록된 기술이 없으면 빈 리스트를 반환합니다.
""")
def get_user_skills(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(UserSkill).filter(UserSkill.user_id == current_user.id).all()

@router.delete("/{skill_id}", status_code=204, summary="보유 기술 삭제", description="""
등록된 기술 중 하나를 삭제합니다.

- `skill_id`는 해당 사용자가 등록한 기술의 고유 ID입니다.
- 본인의 기술만 삭제할 수 있으며, 존재하지 않으면 404 에러를 반환합니다.
- 인증된 사용자만 사용할 수 있습니다.
""")
def delete_user_skill(
    skill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    skill = db.query(UserSkill).filter(UserSkill.id == skill_id, UserSkill.user_id == current_user.id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="해당 보유 기술을 찾을 수 없습니다.")
    db.delete(skill)
    db.commit()
    return
