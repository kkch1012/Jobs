from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.user_skill import UserSkill
from app.models.user_certificate import UserCertificate
from app.schemas.user import (
    UserCreateID, 
    UserCreateEmail,
    UserResponse,
    ResumeUpdate,
    UserResumeResponse
)
from app.utils.dependencies import get_current_user
from app.core.security import get_password_hash

router = APIRouter(prefix="/users", tags=["User"])

@router.post("/signup/id", response_model=UserResponse, summary="ID 기반 회원가입")
def signup_by_id(user_data: UserCreateID, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="이미 존재하는 아이디입니다.")

    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        nickname=user_data.nickname,
        name=user_data.name,
        phone_number=user_data.phone_number,
        birth_date=user_data.birth_date,
        gender=user_data.gender,
        signup_type="id"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/signup/email", response_model=UserResponse, summary="소셜 기반 회원가입")
def signup_by_email(user_data: UserCreateEmail, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="이미 존재하는 이메일입니다.")

    user = User(
        email=user_data.email,
        nickname=user_data.nickname,
        name=user_data.name,
        phone_number=user_data.phone_number,
        birth_date=user_data.birth_date,
        gender=user_data.gender,
        signup_type="email"
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
    data = resume_data.dict(exclude_unset=True, exclude={"skills", "certificates"})
    for field, value in data.items():
        setattr(current_user, field, value)

    # 기술 업데이트
    if resume_data.skills is not None:
        # 기존 기술 삭제
        db.query(UserSkill).filter(UserSkill.user_id == current_user.id).delete()
        # 새로 등록
        for skill in resume_data.skills:
            new_skill = UserSkill(
                user_id=current_user.id,
                skill_id=skill.skill_id,
                proficiency=skill.proficiency
            )
            db.add(new_skill)

    # 자격증 업데이트
    if resume_data.certificates is not None:
        # 기존 자격증 삭제
        db.query(UserCertificate).filter(UserCertificate.user_id == current_user.id).delete()
        # 새로 등록
        for cert in resume_data.certificates:
            new_cert = UserCertificate(
                user_id=current_user.id,
                certificate_id=cert.certificate_id,
                acquired_date=cert.acquired_date
            )
            db.add(new_cert)

    db.commit()
    return {"msg": "이력서 정보가 업데이트되었습니다."}

# 내 이력서 상세 조회 (기술 및 자격증 포함)
@router.get("/me/resume", response_model=UserResumeResponse, summary="내 이력서 상세 조회")
def get_my_resume(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    skills = db.query(UserSkill).filter(UserSkill.user_id == current_user.id).all()
    certificates = db.query(UserCertificate).filter(UserCertificate.user_id == current_user.id).all()

    user.user_skills = skills
    user.user_certificates = certificates

    return user
