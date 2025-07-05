from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.core.security import verify_password, get_password_hash, create_access_token

router = APIRouter(tags=["auth"])


# 토큰 응답 모델
class TokenResponse(BaseModel):
    access_token: str
    token_type: str


# ID 기반 로그인
@router.post(
    "/token",
    summary="아이디 로그인",
    description="username과 password를 받아 로그인합니다.",
    response_model=TokenResponse,
)
def login_by_id(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
    if user.signup_type != "id":
        raise HTTPException(status_code=400, detail="아이디 기반 회원이 아닙니다.")
    access_token = create_access_token({"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


# 소셜 로그인 (이메일 기반, password 없음)
class SocialLoginRequest(BaseModel):
    email: str

@router.post(
    "/login/social",
    summary="소셜 로그인",
    description="소셜 로그인 사용자가 이메일로 로그인합니다. (비밀번호 없이 이메일만 필요)",
    response_model=TokenResponse,
)
def social_login(data: SocialLoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="존재하지 않는 사용자입니다.")
    if user.signup_type != "email":
        raise HTTPException(status_code=400, detail="소셜 로그인 회원이 아닙니다.")
    access_token = create_access_token({"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}
