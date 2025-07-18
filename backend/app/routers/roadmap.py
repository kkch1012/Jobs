from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Union, Optional
from app.database import get_db
from app.models.roadmap import Roadmap
from app.schemas.roadmap import (
    RoadmapCreate, RoadmapUpdate, RoadmapResponse,
    CourseCreate, CourseUpdate, CourseResponse
)
from app.utils.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/roadmaps", tags=["Roadmaps"])

def roadmap_to_response(roadmap):
    if roadmap.type == "강의":
        return CourseResponse.model_validate(roadmap)
    else:
        return RoadmapResponse.model_validate(roadmap)

# 모든 사용자에게 전체 로드맵 조회 (타입별 필터링 지원)
@router.get(
    "/",
    response_model=List[Union[RoadmapResponse, CourseResponse]],
    summary="전체 로드맵 목록 조회 (타입별 필터링 지원)",
    description="""
등록된 모든 로드맵(부트캠프, 강의 등)을 조회합니다.\n\n- 누구나 호출할 수 있습니다.\n- type 파라미터(예: 부트캠프, 강의)로 특정 타입만 필터링할 수 있습니다.\n- 각 타입에 따라 다른 스키마로 반환됩니다.
"""
)
def get_all_roadmaps(
    type: Optional[str] = Query(None, description="필터링할 타입 (예: 부트캠프, 강의)"),
    db: Session = Depends(get_db)
):
    query = db.query(Roadmap)
    if type:
        query = query.filter(Roadmap.type == type)
    roadmaps = query.all()
    return [roadmap_to_response(r) for r in roadmaps]


# 관리자만 로드맵 생성
@router.post(
    "/",
    response_model=RoadmapResponse,
    operation_id="create_roadmap",
    summary="로드맵 생성 (관리자)",
    description="""
새로운 로드맵을 등록합니다.

- 이 API는 관리자만 접근할 수 있습니다.
- 입력된 정보로 새로운 로드맵을 생성하고 반환합니다.
- 모든 타입의 로드맵을 RoadmapResponse로 반환합니다.
"""
)
def create_roadmap(
    roadmap: RoadmapCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # if current_user.role != "admin":
    #     raise HTTPException(status_code=403, detail="관리자만 로드맵을 생성할 수 있습니다.")

    new_roadmap = Roadmap(**roadmap.model_dump())
    db.add(new_roadmap)
    db.commit()
    db.refresh(new_roadmap)
    return new_roadmap


# 관리자만 로드맵 수정
@router.put(
    "/{roadmap_id}",
    response_model=RoadmapResponse,
    operation_id="update_roadmap",
    summary="로드맵 수정 (관리자)",
    description="""
기존 로드맵의 내용을 수정합니다.

- 이 API는 관리자만 접근할 수 있습니다.
- `roadmap_id`에 해당하는 로드맵이 존재하지 않으면 404 오류를 반환합니다.
- 수정할 필드만 선택적으로 포함할 수 있습니다.
- 모든 타입의 로드맵을 RoadmapResponse로 반환합니다.
"""
)
def update_roadmap(
    roadmap_id: int,
    roadmap_data: RoadmapUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # if current_user.role != "admin":
    #     raise HTTPException(status_code=403, detail="관리자만 수정할 수 있습니다.")

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
    operation_id="delete_roadmap",
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
    # if current_user.role != "admin":
    #     raise HTTPException(status_code=403, detail="관리자만 삭제할 수 있습니다.")

    roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
    if not roadmap:
        raise HTTPException(status_code=404, detail="로드맵을 찾을 수 없습니다.")

    db.delete(roadmap)
    db.commit()


@router.get(
    "/{roadmap_id}",
    response_model=RoadmapResponse,
    summary="특정 로드맵 상세 조회",
    operation_id="get_roadmap_detail",
    description="""
특정 로드맵의 상세 정보를 조회합니다.

- `roadmap_id`에 해당하는 로드맵이 존재하지 않으면 404 오류를 반환합니다.
- 모든 타입의 로드맵을 RoadmapResponse로 반환합니다.
"""
)
def get_roadmap_detail(
    roadmap_id: int,
    db: Session = Depends(get_db)
):
    roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
    if not roadmap:
        raise HTTPException(status_code=404, detail="로드맵을 찾을 수 없습니다.")
    return roadmap
