from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.user_skill import UserSkill
from app.models.user_certificate import UserCertificate
from app.schemas.user import (
    UserCreate,
    UserResponse,
    ResumeUpdate,
    UserSkillCreate,
    UserSkillResponse,
    UserCertificateCreate,
    UserCertificateResponse
)
from app.utils.dependencies import get_current_user
from app.core.security import get_password_hash

router = APIRouter(prefix="/users", tags=["User"])

# 회원가입
@router.post("/signup", response_model=UserResponse, summary="회원가입", description="""
회원 정보를 입력받아 회원가입을 수행합니다.

- `signup_type`이 `"id"`인 경우 `username`으로 가입
- `signup_type`이 `"email"`인 경우 `email`로 가입
- 이메일 또는 아이디 중복 시 400 에러 반환
""")
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    if user_data.signup_type == "id":
        if not user_data.username:
            raise HTTPException(status_code=400, detail="아이디(username)는 필수입니다.")
        if db.query(User).filter(User.username == user_data.username).first():
            raise HTTPException(status_code=400, detail="이미 존재하는 아이디입니다.")
    elif user_data.signup_type == "email":
        if not user_data.email:
            raise HTTPException(status_code=400, detail="이메일은 필수입니다.")
        if db.query(User).filter(User.email == user_data.email).first():
            raise HTTPException(status_code=400, detail="이미 존재하는 이메일입니다.")
    else:
        raise HTTPException(status_code=400, detail="signup_type은 'id' 또는 'email'만 가능합니다.")

    user = User(
        username=user_data.username if user_data.signup_type == "id" else None,
        email=user_data.email if user_data.signup_type == "email" else None,
        hashed_password=get_password_hash(user_data.password),
        nickname=user_data.nickname,
        name=user_data.name,
        phone_number=user_data.phone_number,
        birth_date=user_data.birth_date,
        gender=user_data.gender,
        signup_type=user_data.signup_type,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# 내 정보 조회
@router.get("/me", response_model=UserResponse, summary="내 정보 조회", description="""
현재 로그인된 사용자의 정보를 조회합니다.

- 인증이 필요합니다 (Bearer Token).
""")
def get_my_profile(current_user: User = Depends(get_current_user)):
    return current_user

# 이력서(프로필) 업데이트
@router.put("/me/resume", summary="이력서 정보 입력/수정")
def update_resume(
    resume_data: ResumeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    for field, value in resume_data.dict(exclude_unset=True).items():
        setattr(current_user, field, value)
    db.commit()
    return {"msg": "이력서 정보가 업데이트되었습니다."}

# 사용자 기술 등록
@router.post("/me/skills", response_model=UserSkillResponse, summary="보유 기술 추가", description="""
사용자의 이력서에 기술을 추가합니다.

- `skill_id`: 사전에 등록된 기술 ID
- `proficiency`: 사용자의 숙련도 (예: 1~5)
- 인증된 사용자만 사용할 수 있습니다.
""")
def add_user_skill(
    skill_data: UserSkillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_skill = UserSkill(
        user_id=current_user.id,
        skill_id=skill_data.skill_id,
        proficiency=skill_data.proficiency
    )
    db.add(user_skill)
    db.commit()
    db.refresh(user_skill)
    return user_skill

# 사용자 기술 목록 조회
@router.get("/me/skills", response_model=List[UserSkillResponse], summary="보유 기술 목록", description="""
로그인한 사용자가 등록한 기술 목록을 조회합니다.

- 인증된 사용자만 접근 가능
- 등록된 기술이 없으면 빈 리스트를 반환합니다.
""")
def get_user_skills(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(UserSkill).filter(UserSkill.user_id == current_user.id).all()

# 사용자 기술 삭제
@router.delete("/me/skills/{skill_id}", status_code=204, summary="보유 기술 삭제", description="""
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

# 사용자 자격증 등록
@router.post("/me/certificates", response_model=UserCertificateResponse, summary="자격증 추가", description="""
사용자가 본인의 자격증을 추가합니다.

- 자격증은 사전에 관리자에 의해 등록된 항목에서 선택해야 합니다.
- 사용자 인증이 필요합니다.
""")
def add_user_certificate(
    data: UserCertificateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_cert = UserCertificate(
        user_id=current_user.id,
        certificate_id=data.certificate_id,
        acquired_date=data.acquired_date
    )
    db.add(user_cert)
    db.commit()
    db.refresh(user_cert)
    return user_cert

# 사용자 자격증 목록 조회
@router.get("/me/certificates", response_model=List[UserCertificateResponse], summary="자격증 목록", description="""
로그인된 사용자가 보유한 자격증 목록을 조회합니다.

- 인증된 사용자만 접근 가능합니다.
""")
def get_my_certificates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(UserCertificate).filter(UserCertificate.user_id == current_user.id).all()

# 사용자 자격증 삭제
@router.delete("/me/certificates/{cert_id}", status_code=204, summary="자격증 삭제", description="""
보유 중인 자격증 중 하나를 삭제합니다.

- 본인 소유의 자격증만 삭제 가능
- 인증이 필요합니다.
""")
def delete_user_certificate(
    cert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cert = db.query(UserCertificate).filter(UserCertificate.id == cert_id, UserCertificate.user_id == current_user.id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="자격증 기록을 찾을 수 없습니다.")
    db.delete(cert)
    db.commit()
    return
