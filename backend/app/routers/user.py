from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import httpx
import os
from app.database import get_db
from app.models.user import User
from app.models.user_skill import UserSkill
from app.models.user_certificate import UserCertificate
from app.schemas.user import (
    UserCreateID, 
    UserCreateEmail,
    UserResponse,
    ResumeUpdate,
    UserResumeResponse,
    NaverCallbackRequest,
    NaverUserInfo,
    UserCreateNaver
)
from app.utils.dependencies import get_current_user, get_optional_current_user
from app.core.security import get_password_hash
from app.models.skill import Skill
from app.models.certificate import Certificate
from app.models.user_experience import UserExperience
from app.services.similarity_scores import auto_compute_user_similarity
from app.services.jobs_gap import get_job_recommendation_simple
from app.utils.logger import app_logger 

router = APIRouter(prefix="/users", tags=["User"])

@router.post("/signup/id"
             ,response_model=UserResponse, 
             operation_id="signup_by_id",
             summary="ID 기반 회원가입")
def signup_by_id(user_data: UserCreateID, db: Session = Depends(get_db)):
    # 이메일 중복 체크
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="이미 존재하는 아이디입니다.")
    
    # 닉네임 중복 체크
    if db.query(User).filter(User.nickname == user_data.nickname).first():
        raise HTTPException(status_code=400, detail="이미 존재하는 닉네임입니다.")

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

@router.post("/signup/email", 
             response_model=UserResponse,
             operation_id="signup_by_email",
             summary="이메일 기반 (소셜 로그인) 회원가입")
def signup_by_email(user_data: UserCreateEmail, db: Session = Depends(get_db)):
    # 이메일 중복 체크
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="이미 존재하는 이메일입니다.")
    
    # 닉네임 중복 체크
    if db.query(User).filter(User.nickname == user_data.nickname).first():
        raise HTTPException(status_code=400, detail="이미 존재하는 닉네임입니다.")

    user = User(
        email=user_data.email,
        nickname=user_data.nickname,
        name=user_data.name,
        phone_number=user_data.phone_number,
        birth_date=user_data.birth_date,
        gender=user_data.gender,
        signup_type="email",
        hashed_password=None  # 소셜 로그인은 비밀번호 없음
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/signup/naver",
             response_model=UserResponse,
             operation_id="signup_by_naver", 
             summary="네이버 OAuth 회원가입")
async def signup_by_naver(data: NaverCallbackRequest, db: Session = Depends(get_db)):
    """네이버 OAuth 콜백을 받아서 회원가입을 처리합니다."""
    try:
        # 1. Access Token 획득
        token_url = "https://nid.naver.com/oauth2.0/token"
        token_data = {
            "grant_type": "authorization_code",
            "client_id": os.getenv("NAVER_CLIENT_ID"),
            "client_secret": os.getenv("NAVER_CLIENT_SECRET"),
            "code": data.code,
            "state": data.state,
        }
        
        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=token_data)
            token_json = token_response.json()
            
            if "access_token" not in token_json:
                raise HTTPException(status_code=400, detail="네이버 토큰 획득 실패")
            
            access_token = token_json["access_token"]
            
            # 2. 사용자 정보 조회
            user_info_url = "https://openapi.naver.com/v1/nid/me"
            headers = {"Authorization": f"Bearer {access_token}"}
            
            user_response = await client.get(user_info_url, headers=headers)
            user_json = user_response.json()
            
            if user_json.get("resultcode") != "00":
                raise HTTPException(status_code=400, detail="네이버 사용자 정보 조회 실패")
            
            naver_user = user_json["response"]
            email = naver_user.get("email")
            name = naver_user.get("name")
            nickname = naver_user.get("nickname")
            
            if not email:
                raise HTTPException(status_code=400, detail="이메일 정보를 가져올 수 없습니다")
            
            # 3. 중복 확인
            existing_user = db.query(User).filter(User.email == email).first()
            if existing_user:
                raise HTTPException(status_code=400, detail="이미 가입된 이메일입니다")
            
            # 닉네임 중복 확인 및 자동 생성
            original_nickname = nickname or email.split("@")[0]
            final_nickname = original_nickname
            counter = 1
            
            while db.query(User).filter(User.nickname == final_nickname).first():
                final_nickname = f"{original_nickname}_{counter}"
                counter += 1
            
            # 4. 신규 사용자 생성
            user = User(
                email=email,
                name=name or nickname or email.split("@")[0],
                nickname=final_nickname,
                signup_type="naver",
                hashed_password=None,  # 소셜 로그인은 비밀번호 없음
                phone_number="",  # 네이버에서 제공하지 않는 정보는 빈값
                birth_date=None,
                gender=""
            )
            
            db.add(user)
            db.commit()
            db.refresh(user)
            
            app_logger.info(f"네이버 OAuth 회원가입 완료: {email}")
            return user
            
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"네이버 회원가입 처리 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"회원가입 처리 중 오류가 발생했습니다: {str(e)}")

# 내 정보 조회
@router.get("/me", response_model=UserResponse, 
            operation_id="get_my_profile",
            summary="내 정보 조회", description="""
현재 로그인된 사용자의 정보를 조회합니다.

- 인증이 필요합니다 (Bearer Token).
""")
def get_my_profile(current_user: User = Depends(get_current_user)):
    return current_user

# 이력서(프로필) 업데이트

@router.put("/me/resume", 
            operation_id="update_resume",
            summary="이력서 정보 입력/수정")
def update_resume(
    resume_data: ResumeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # User 기본 필드 업데이트 (skills, certificates, experience 제외)
    data = resume_data.dict(exclude_unset=True, exclude={"skills", "certificates", "experience"})
    for field, value in data.items():
        setattr(current_user, field, value)

    # 기술 업데이트
    if resume_data.skills is not None:
        db.query(UserSkill).filter(UserSkill.user_id == current_user.id).delete()
        for skill in resume_data.skills:
            skill_obj = db.query(Skill).filter(Skill.name == skill.skill_name).first()
            if not skill_obj:
                raise HTTPException(status_code=400, detail=f"등록되지 않은 스킬명입니다: {skill.skill_name}")
            new_skill = UserSkill(user_id=current_user.id, skill_id=skill_obj.id, proficiency=skill.proficiency)
            db.add(new_skill)

    # 자격증 업데이트
    if resume_data.certificates is not None:
        db.query(UserCertificate).filter(UserCertificate.user_id == current_user.id).delete()
        for cert in resume_data.certificates:
            cert_obj = db.query(Certificate).filter(Certificate.name == cert.certificate_name).first()
            if not cert_obj:
                raise HTTPException(status_code=400, detail=f"등록되지 않은 자격증명입니다: {cert.certificate_name}")
            new_cert = UserCertificate(user_id=current_user.id, certificate_id=cert_obj.id, acquired_date=cert.acquired_date)
            db.add(new_cert)

    # 경험 업데이트
    if resume_data.experience is not None:
        db.query(UserExperience).filter(UserExperience.user_id == current_user.id).delete()
        for exp in resume_data.experience:
            new_exp = UserExperience(
                user_id=current_user.id,
                type=exp.type,
                name=exp.name,
                period=exp.period,
                description=exp.description
            )
            db.add(new_exp)

    db.commit()
    
    # 이력서 업데이트 후 유사도 점수 자동 재계산
    try:
        from app.models.job_post import JobPost
        job_posts = db.query(JobPost).filter(JobPost.full_embedding.isnot(None)).all()
        auto_compute_user_similarity(current_user, db, job_posts)
    except Exception as e:
        # 유사도 계산 실패해도 이력서 업데이트는 성공으로 처리
        app_logger.error(f"유사도 자동 계산 실패: {str(e)}")
    return {"msg": "이력서 정보가 업데이트되었습니다."}

@router.get("/me/resume", 
            operation_id="get_my_resume",
            response_model=UserResumeResponse, summary="내 이력서 상세 조회")
def get_my_resume(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    skills = db.query(UserSkill).filter(UserSkill.user_id == current_user.id).all()
    certificates = db.query(UserCertificate).filter(UserCertificate.user_id == current_user.id).all()
    experiences = db.query(UserExperience).filter(UserExperience.user_id == current_user.id).all()

    skill_list = []
    for us in skills:
        skill_obj = db.query(Skill).filter(Skill.id == us.skill_id).first()
        skill_list.append({
            "skill_name": skill_obj.name if skill_obj else "", 
            "proficiency": us.proficiency,
            "skill_id": us.skill_id
        })

    certificate_list = []
    for uc in certificates:
        cert_obj = db.query(Certificate).filter(Certificate.id == uc.certificate_id).first()
        certificate_list.append({
            "certificate_name": cert_obj.name if cert_obj else "", 
            "acquired_date": uc.acquired_date,
            "id": uc.id
        })

    experience_list = []
    for ue in experiences:
        experience_list.append({
            "type": ue.type,
            "name": ue.name,
            "period": ue.period,
            "description": ue.description,
            "id": ue.id
        })

    return {
        "id": user.id,
        "email": user.email,
        "nickname": user.nickname,
        "name": user.name,
        "phone_number": user.phone_number,
        "university": user.university,
        "major": user.major,
        "gpa": user.gpa,
        "education_status": user.education_status,
        "degree": user.degree,
        "language_score": user.language_score,
        "desired_job": user.desired_job,
        "experience": experience_list,
        "working_year": user.working_year,
        "skills": skill_list,
        "certificates": certificate_list
    }

@router.get("/desired-job", 
            operation_id="get_desired_job",
            summary="희망직무 조회",
            description="""
회원/비회원 모두 사용할 수 있는 희망직무 조회 엔드포인트입니다.

- 인증이 필요하지 않습니다.
- 회원인 경우: 설정된 희망직무를 반환합니다.
- 회원이지만 희망직무가 없는 경우: 직무 추천 시스템을 통해 추천된 직무를 반환합니다.
- 비회원인 경우: "프론트엔드 개발자"를 기본값으로 반환합니다.
- 희망직무가 여러 개인 경우 첫 번째 희망직무를 반환합니다.

**응답 예시:**
```
"백엔드 개발자"
```
""")
def get_desired_job(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    회원/비회원 모두 사용할 수 있는 희망직무 조회 엔드포인트입니다.
    """
    try:
        # 비회원인 경우
        if not current_user:
            return "프론트엔드 개발자"
        
        # 디버그 정보는 로거로 대체
        app_logger.debug(f"희망직무 조회 - 사용자 ID: {current_user.id}, 희망직무: {current_user.desired_job}")
        
        # 회원이지만 희망직무가 없는 경우 - 직무 추천 시스템 연동
        if not current_user.desired_job:
            try:
                # 간단한 직무 추천 시스템 호출
                recommended_job = get_job_recommendation_simple(current_user, db)
                if recommended_job:
                    return recommended_job
                else:
                    # 추천 실패 시 기본값 반환
                    return "프론트엔드 개발자"
            except Exception as e:
                # 추천 시스템 오류 시 기본값 반환
                app_logger.error(f"직무 추천 시스템 오류: {str(e)}")
                return "프론트엔드 개발자"
        
        # 희망직무가 리스트인 경우 첫 번째 항목 반환, 문자열인 경우 그대로 반환
        if isinstance(current_user.desired_job, list):
            if len(current_user.desired_job) > 0:
                app_logger.debug(f"리스트에서 첫 번째 희망직무 반환: {current_user.desired_job[0]}")
                return current_user.desired_job[0]
            else:
                app_logger.debug("빈 리스트이므로 기본값 반환")
                return "프론트엔드 개발자"
        else:
            # 문자열인 경우
            app_logger.debug(f"문자열 희망직무 반환: {current_user.desired_job}")
            return current_user.desired_job
            
    except Exception as e:
        # 기타 예외 발생 시 (비회원으로 처리)
        app_logger.error(f"희망직무 조회 중 예외 발생: {str(e)}")
        return "프론트엔드 개발자"

