from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user_preference import UserPreference
from app.schemas.user_preference import UserPreferenceCreate, UserPreferenceResponse
from app.utils.dependencies import get_current_user
from app.models.user import User
from typing import List


router = APIRouter(prefix="/preferences", tags=["User Preferences"])

@router.get(
    "/",
    response_model=List[UserPreferenceResponse],
    operation_id="get_preferences",
    summary="찜한 채용공고 목록 조회",
    description="""
사용자가 찜한 모든 채용공고 목록을 조회합니다.

- 로그인한 사용자의 찜한 공고 리스트를 반환합니다.
- 각 찜한 공고에 연결된 공고 상세 정보도 함께 포함됩니다.
"""
)
def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    prefs = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).all()
    return prefs


@router.post(
    "/",
    response_model=UserPreferenceResponse,
    operation_id="add_preference",
    summary="채용공고 찜하기",
    description="""
사용자가 특정 채용공고를 찜(즐겨찾기)합니다.

- `job_post_id`는 찜하려는 채용공고의 ID입니다.
- 동일한 공고를 중복으로 찜하려는 경우 `400 Bad Request` 에러가 발생합니다.
- 성공 시 등록된 찜 정보를 반환합니다.
"""
)
def add_preference(
    preference: UserPreferenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    existing = (
        db.query(UserPreference)
        .filter_by(user_id=current_user.id, job_post_id=preference.job_post_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 찜한 공고입니다."
        )

    new_pref = UserPreference(user_id=current_user.id, job_post_id=preference.job_post_id)
    db.add(new_pref)
    db.commit()
    db.refresh(new_pref)
    return new_pref

@router.delete(
    "/{job_post_id}",
    status_code=204,
    summary="찜한 채용공고 삭제",
    operation_id="remove_preference",
    description="""
사용자가 찜한 채용공고를 삭제합니다.

- `job_post_id`는 삭제할 찜 공고의 ID입니다.
- 사용자가 찜하지 않은 공고 ID로 요청 시 `404 Not Found` 오류가 발생합니다.
- 성공 시 본문 없이 `204 No Content` 응답을 반환합니다.
"""
)
def remove_preference(
    job_post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pref = (
        db.query(UserPreference)
        .filter_by(user_id=current_user.id, job_post_id=job_post_id)
        .first()
    )
    if not pref:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="찜한 공고가 없습니다."
        )
    db.delete(pref)
    db.commit()
