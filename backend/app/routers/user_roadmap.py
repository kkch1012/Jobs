from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user_roadmap import UserRoadmap
from app.schemas.user_roadmap import UserRoadmapCreate, UserRoadmapResponse
from typing import List
from app.utils.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/user_roadmaps", tags=["UserRoadmap"])

# 로드맵 찜하기
@router.post(
    "/",
    response_model=UserRoadmapResponse,
    operation_id="create_user_roadmap",
    summary="로드맵 찜하기",
    description="""
현재 로그인한 사용자가 특정 로드맵을 찜(저장)합니다.

- `roadmaps_id`는 찜할 로드맵의 ID입니다.
- 동일한 로드맵을 중복으로 찜하려는 경우 `400 Bad Request` 에러가 발생합니다.
- 성공 시 등록된 찜 로드맵 정보를 반환합니다.
"""
)
def create_user_roadmap(
    roadmap_data: UserRoadmapCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # 중복 체크
        existing = db.query(UserRoadmap).filter_by(
            user_id=current_user.id,
            roadmaps_id=roadmap_data.roadmaps_id
        ).first()
        
        if existing:
            print(f"중복 찜 시도: 사용자 {current_user.id}가 로드맵 {roadmap_data.roadmaps_id}를 이미 찜했습니다.")
            raise HTTPException(
                status_code=400, 
                detail=f"이미 찜한 로드맵입니다. (로드맵 ID: {roadmap_data.roadmaps_id})"
            )

        # 로드맵 존재 여부 확인
        from app.models.roadmap import Roadmap
        roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_data.roadmaps_id).first()
        if not roadmap:
            raise HTTPException(
                status_code=404, 
                detail=f"존재하지 않는 로드맵입니다. (로드맵 ID: {roadmap_data.roadmaps_id})"
            )

        new_roadmap = UserRoadmap(user_id=current_user.id, roadmaps_id=roadmap_data.roadmaps_id)
        db.add(new_roadmap)
        db.commit()
        db.refresh(new_roadmap)
        
        print(f"로드맵 찜 성공: 사용자 {current_user.id}가 로드맵 {roadmap_data.roadmaps_id}를 찜했습니다.")
        return new_roadmap
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"로드맵 찜 중 오류 발생: {str(e)}")
        print(f"오류 상세: {traceback.format_exc()}")
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail=f"로드맵 찜 중 서버 오류가 발생했습니다: {str(e)}"
        )

# 내 찜한 로드맵 목록
@router.get(
    "/me",
    response_model=List[UserRoadmapResponse],
    operation_id="get_my_roadmaps",
    summary="내 찜한 로드맵 목록",
    description="""
로그인한 사용자가 찜한 로드맵 목록을 조회합니다.

- 로그인된 사용자 기준으로 본인의 찜 목록만 조회됩니다.
- 각 찜한 로드맵에 연결된 로드맵 상세 정보도 함께 포함됩니다.
"""
)
def get_my_roadmaps(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 로드맵 정보를 포함하여 조회
    from app.models.roadmap import Roadmap
    user_roadmaps = (
        db.query(UserRoadmap)
        .join(Roadmap, UserRoadmap.roadmaps_id == Roadmap.id)
        .filter(UserRoadmap.user_id == current_user.id)
        .all()
    )
    return user_roadmaps

# 찜한 로드맵 삭제
@router.delete(
    "/{roadmap_id}",
    status_code=204,
    summary="찜한 로드맵 삭제",
    operation_id="delete_user_roadmap",
    description="""
찜한 로드맵을 삭제합니다.

- `roadmap_id`는 삭제할 로드맵의 ID입니다.
- 사용자가 찜하지 않은 로드맵 ID로 요청 시 `404 Not Found` 오류가 발생합니다.
- 성공 시 본문 없이 `204 No Content` 응답을 반환합니다.
"""
)
def delete_user_roadmap(
    roadmap_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    roadmap = db.query(UserRoadmap).filter_by(
        user_id=current_user.id,
        roadmaps_id=roadmap_id
    ).first()
    if not roadmap:
        raise HTTPException(status_code=404, detail="찜한 로드맵이 없습니다.")
    db.delete(roadmap)
    db.commit()
