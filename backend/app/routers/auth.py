from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import timedelta

from app.database import get_db
from app.models.user import User
from app.core.security import verify_password, get_password_hash, create_access_token
from app.utils.exceptions import UnauthorizedException, BadRequestException

router = APIRouter(tags=["auth"])


# 토큰 응답 모델
class TokenResponse(BaseModel):
    access_token: str
    token_type: str


# ID 기반 로그인
@router.post(
    "/token",
    summary="아이디 로그인",
    operation_id="login_by_id",
    description="username과 password를 받아 로그인합니다.",
    response_model=TokenResponse,
)
def login_by_id(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user:
        raise UnauthorizedException("아이디 또는 비밀번호가 올바르지 않습니다.")
    if not getattr(user, 'hashed_password', None):
        raise UnauthorizedException("아이디 또는 비밀번호가 올바르지 않습니다.")
    if not verify_password(form_data.password, getattr(user, 'hashed_password')):
        raise UnauthorizedException("아이디 또는 비밀번호가 올바르지 않습니다.")
    if getattr(user, 'signup_type', None) != "id":
        raise BadRequestException("아이디 기반 회원이 아닙니다.")
    access_token = create_access_token(
        {"sub": str(user.id)}, 
        expires_delta=timedelta(days=1)  # 7일로 토큰 만료 시간 설정
    )
    return {"access_token": access_token, "token_type": "bearer"}


# 소셜 로그인 (이메일 기반, password 없음)
class SocialLoginRequest(BaseModel):
    email: str

@router.post(
    "/login/social",
    summary="소셜 로그인",
    operation_id="social_login",
    description="소셜 로그인 사용자가 이메일로 로그인합니다. (비밀번호 없이 이메일만 필요)",
    response_model=TokenResponse,
)
def social_login(data: SocialLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise UnauthorizedException("존재하지 않는 사용자입니다.")
    if getattr(user, 'signup_type', None) != "email":
        raise BadRequestException("소셜 로그인 회원이 아닙니다.")
    access_token = create_access_token(
        {"sub": str(user.id)}, 
        expires_delta=timedelta(days=1)  # 7일로 토큰 만료 시간 설정
    )
    return {"access_token": access_token, "token_type": "bearer"}
