from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user_skill import UserSkill
from app.schemas.user_skill import UserSkillCreate, UserSkillResponse
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.models.skill import Skill
from app.utils.logger import app_logger
import re
from pydantic import BaseModel

class UpdateSkillProficiencyRequest(BaseModel):
    skill_name: str
    proficiency: str

router = APIRouter(prefix="/users/me/skills", tags=["UserSkill"])

def normalize_skill_name(skill_name: str) -> str:
    """스킬명을 정규화합니다 (대소문자, 한글/영어 매핑)"""
    skill_name = skill_name.strip().lower()
    
    # 한글 -> 영어 매핑
    korean_to_english = {
        "파이썬": "python",
        "자바": "java",
        "자바스크립트": "javascript",
        "씨샵": "c#",
        "씨플플": "c++",
        "씨언어": "c",
        "리액트": "react",
        "뷰": "vue",
        "앵귤러": "angular",
        "노드": "node.js",
        "스프링": "spring",
        "장고": "django",
        "플라스크": "flask",
        "도커": "docker",
        "쿠버네티스": "kubernetes",
        "마이에스큐엘": "mysql",
        "포스트그레": "postgresql",
        "몽고디비": "mongodb",
        "레디스": "redis",
        "깃": "git",
        "깃허브": "github",
        "아마존웹서비스": "aws",
        "구글클라우드": "gcp",
        "마이크로소프트애저": "azure"
    }
    
    # 한글명이 있으면 영어로 변환
    if skill_name in korean_to_english:
        skill_name = korean_to_english[skill_name]
    
    # 공백 제거 및 특수문자 정리
    skill_name = re.sub(r'[^\w\s#\+\.\-]', '', skill_name)
    skill_name = re.sub(r'\s+', ' ', skill_name).strip()
    
    return skill_name

def find_similar_skill(db: Session, skill_name: str) -> Skill:
    """정규화된 스킬명으로 유사한 스킬을 찾습니다"""
    normalized_input = normalize_skill_name(skill_name)
    
    # 모든 스킬을 가져와서 정규화하여 비교
    all_skills = db.query(Skill).all()
    for skill in all_skills:
        if normalize_skill_name(skill.name) == normalized_input:
            return skill
    
    return None

@router.post("/", 
             response_model=UserSkillResponse, 
             summary="보유 기술 추가", 
             operation_id="add_user_skill_by_name",
             description="""
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
    # 스킬 테이블에서 해당 이름의 스킬 조회
    skill = db.query(Skill).filter(Skill.name == skill_data.skill_name).first()
    if not skill:
        raise HTTPException(status_code=404, detail="스킬을 찾을 수 없습니다.")
    
    # 해당 유저가 이미 같은 스킬을 등록했는지 확인
    existing_user_skill = (
        db.query(UserSkill)
          .filter(UserSkill.user_id == current_user.id, UserSkill.skill_id == skill.id)
          .first()
    )
    if existing_user_skill:
        raise HTTPException(status_code=400, detail="이미 등록된 기술입니다.")
    
    # 새 UserSkill 생성 및 저장
    user_skill = UserSkill(
        user_id=getattr(current_user, 'id'),
        skill_id=getattr(skill, 'id'),
        proficiency=skill_data.proficiency
    )
    db.add(user_skill)
    db.commit()
    db.refresh(user_skill)

    return UserSkillResponse(
        skill_name=getattr(skill, 'name'),
        proficiency=getattr(user_skill, 'proficiency')
    )

@router.post("/smart-add", 
             summary="스마트 기술 추가", 
             operation_id="smart_add_user_skill",
             description="""
사용자의 이력서에 기술을 스마트하게 추가합니다.
- 스킬명 정규화 지원 (한글/영어, 대소문자 무관)
- 중복 검사 및 숙련도 업데이트 옵션 제공
- `skill_name`: 스킬 이름 (한글/영어 모두 지원)
- `proficiency`: 숙련도 (선택사항)
- 인증된 사용자만 사용할 수 있습니다.
""")
def smart_add_user_skill(
    skill_data: dict,  # UserSkillCreate에서 dict로 변경
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # dict에서 데이터 추출
    skill_name = skill_data.get("skill_name")
    proficiency = skill_data.get("proficiency")
    
    if not skill_name:
        return {
            "status": "error",
            "message": "스킬명을 입력해주세요."
        }
    
    # 스킬명 정규화
    normalized_skill_name = normalize_skill_name(skill_name)
    
    # 정규화된 스킬명으로 스킬 찾기
    skill = find_similar_skill(db, skill_name)
    
    if not skill:
        # 정확히 일치하는 스킬이 없으면 원본명으로 다시 검색
        skill = db.query(Skill).filter(Skill.name == skill_name).first()
        if not skill:
            return {
                "status": "skill_not_found",
                "message": f"'{skill_name}' 스킬을 찾을 수 없습니다. 정확한 스킬명을 입력해주세요.",
                "normalized_name": normalized_skill_name
            }
    
    # 해당 유저가 이미 같은 스킬을 등록했는지 확인
    existing_user_skill = (
        db.query(UserSkill)
          .filter(UserSkill.user_id == current_user.id, UserSkill.skill_id == skill.id)
          .first()
    )
    
    if existing_user_skill:
        return {
            "status": "duplicate",
            "message": f"이미 '{skill.name}' 스킬이 등록되어 있습니다. 숙련도를 바꿔드릴까요?",
            "current_proficiency": existing_user_skill.proficiency,
            "skill_name": skill.name,
            "skill_id": existing_user_skill.id
        }
    
    # 숙련도가 없으면 입력 요청
    if not proficiency or proficiency.strip() == "":
        return {
            "status": "need_proficiency",
            "message": f"'{skill.name}' 스킬의 숙련도를 입력해주세요. (예: 초급, 중급, 고급, 또는 1-5점)",
            "skill_name": skill.name,
            "skill_id": skill.id
        }
    
    # 새 UserSkill 생성 및 저장
    user_skill = UserSkill(
        user_id=current_user.id,
        skill_id=skill.id,
        proficiency=proficiency
    )
    db.add(user_skill)
    db.commit()
    db.refresh(user_skill)

    return {
        "status": "success",
        "message": f"'{skill.name}' 스킬이 성공적으로 추가되었습니다.",
        "skill_name": skill.name,
        "proficiency": user_skill.proficiency
    }

@router.put("/update-proficiency/{skill_id}",
            summary="스킬 숙련도 업데이트",
            operation_id="update_skill_proficiency",
            description="기존 스킬의 숙련도를 업데이트합니다.")
def update_skill_proficiency(
    skill_id: int,
    proficiency: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_skill = (
        db.query(UserSkill)
          .filter(UserSkill.id == skill_id, UserSkill.user_id == current_user.id)
          .first()
    )
    
    if not user_skill:
        raise HTTPException(status_code=404, detail="해당 스킬을 찾을 수 없습니다.")
    
    user_skill.proficiency = proficiency
    db.commit()
    db.refresh(user_skill)
    
    # 스킬명도 함께 반환
    skill = db.query(Skill).filter(Skill.id == user_skill.skill_id).first()
    
    return {
        "status": "success",
        "message": f"'{skill.name}' 스킬의 숙련도가 '{proficiency}'로 업데이트되었습니다.",
        "skill_name": skill.name,
        "proficiency": proficiency
    }

@router.put("/update-proficiency-by-name",
            summary="스킬명으로 숙련도 업데이트", 
            operation_id="update_skill_proficiency_by_name",
            description="스킬명을 이용해 기존 스킬의 숙련도를 업데이트합니다.")
def update_skill_proficiency_by_name(
    request: UpdateSkillProficiencyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 스킬명 정규화
    normalized_skill = normalize_skill_name(request.skill_name)
    
    # 스킬 찾기
    skill = find_similar_skill(db, normalized_skill)
    if not skill:
        raise HTTPException(status_code=404, detail=f"'{request.skill_name}' 스킬을 찾을 수 없습니다.")
    
    # 사용자의 해당 스킬 찾기
    user_skill = (
        db.query(UserSkill)
          .filter(UserSkill.skill_id == skill.id, UserSkill.user_id == current_user.id)
          .first()
    )
    
    if not user_skill:
        raise HTTPException(status_code=404, detail=f"'{skill.name}' 스킬을 보유하고 있지 않습니다.")
    
    # 숙련도 업데이트
    old_proficiency = user_skill.proficiency
    user_skill.proficiency = request.proficiency
    db.commit()
    db.refresh(user_skill)
    
    return {
        "status": "success",
        "message": f"'{skill.name}' 스킬의 숙련도가 '{old_proficiency}'에서 '{request.proficiency}'로 업데이트되었습니다.",
        "skill_name": skill.name,
        "old_proficiency": old_proficiency,
        "new_proficiency": request.proficiency
    }

@router.get("/", 
            response_model=List[UserSkillResponse], 
            operation_id="get_user_skills",
            summary="보유 기술 목록", description="""
로그인한 사용자가 등록한 기술 목록을 조회합니다.

- 인증된 사용자만 접근 가능
- skill_name 파라미터로 특정 스킬만 조회 가능
- 등록된 기술이 없으면 빈 리스트를 반환합니다.
""")
def get_user_skills(
    skill_name: Optional[str] = Query(None, description="특정 스킬명으로 필터링 (선택사항)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = (
        db.query(UserSkill, Skill.name.label("skill_name"))
          .join(Skill, UserSkill.skill_id == Skill.id)
          .filter(UserSkill.user_id == current_user.id)
    )
    
    # 특정 스킬명으로 필터링
    if skill_name:
        normalized_skill = normalize_skill_name(skill_name)
        query = query.filter(Skill.name.ilike(f"%{normalized_skill}%"))
    
    user_skills = query.all()
    # 디버깅용 로그 출력
    app_logger.debug(f"사용자 스킬 조회: {len(user_skills)}개")
    # UserSkill 객체와 skill_name 튜플을 UserSkillResponse 리스트로 변환
    return [
    UserSkillResponse(
        skill_id=getattr(user_skill, 'id'),
        skill_name=skill_name,
        proficiency=getattr(user_skill, 'proficiency')
    )
    for user_skill, skill_name in user_skills
]


@router.delete("/{skill_id}",
               status_code=204, 
               operation_id="delete_user_skill",
               summary="보유 기술 삭제", description="""
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
