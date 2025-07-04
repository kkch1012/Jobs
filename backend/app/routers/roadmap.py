from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.roadmap import Roadmap
from app.schemas.roadmap import RoadmapCreate, RoadmapUpdate, RoadmapResponse
from app.utils.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/roadmaps", tags=["Roadmaps"])

# 모든 사용자에게 전체 로드맵 조회
@router.get(
    "/",
    response_model=list[RoadmapResponse],
    summary="전체 로드맵 조회",
    description="""
모든 사용자가 등록된 전체 로드맵 목록을 조회할 수 있습니다.

- 인증 여부와 관계없이 누구나 호출 가능합니다.
- 반환 결과는 `RoadmapResponse` 리스트입니다.
"""
)
def get_all_roadmaps(db: Session = Depends(get_db)):
    return db.query(Roadmap).all()


# 관리자만 로드맵 생성
@router.post(
    "/",
    response_model=RoadmapResponse,
    summary="로드맵 생성 (관리자)",
    description="""
새로운 로드맵을 등록합니다.

- 이 API는 관리자만 접근할 수 있습니다.
- 입력된 정보로 새로운 로드맵을 생성하고 반환합니다.
"""
)
def create_roadmap(
    roadmap: RoadmapCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자만 로드맵을 생성할 수 있습니다.")

    new_roadmap = Roadmap(**roadmap.model_dump())
    db.add(new_roadmap)
    db.commit()
    db.refresh(new_roadmap)
    return new_roadmap


# 관리자만 로드맵 수정
@router.put(
    "/{roadmap_id}",
    response_model=RoadmapResponse,
    summary="로드맵 수정 (관리자)",
    description="""
기존 로드맵의 내용을 수정합니다.

- 이 API는 관리자만 접근할 수 있습니다.
- `roadmap_id`에 해당하는 로드맵이 존재하지 않으면 404 오류를 반환합니다.
- 수정할 필드만 선택적으로 포함할 수 있습니다.
"""
)
def update_roadmap(
    roadmap_id: int,
    roadmap_data: RoadmapUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자만 수정할 수 있습니다.")

    roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
    if not roadmap:
        raise HTTPException(status_code=404, detail="로드맵을 찾을 수 없습니다.")

    for field, value in roadmap_data.model_dump(exclude_unset=True).items():
        setattr(roadmap, field, value)

    db.commit()
    db.refresh(roadmap)
    return roadmap


# 관리자만 로드맵 삭제
@router.delete(
    "/{roadmap_id}",
    status_code=204,
    summary="로드맵 삭제 (관리자)",
    description="""
로드맵을 삭제합니다.

- 이 API는 관리자만 접근할 수 있습니다.
- `roadmap_id`에 해당하는 로드맵이 존재하지 않으면 404 오류를 반환합니다.
- 성공 시 본문 없이 `204 No Content` 응답을 반환합니다.
"""
)
def delete_roadmap(
    roadmap_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자만 삭제할 수 있습니다.")

    roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
    if not roadmap:
        raise HTTPException(status_code=404, detail="로드맵을 찾을 수 없습니다.")

    db.delete(roadmap)
    db.commit()
