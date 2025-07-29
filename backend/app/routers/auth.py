from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import timedelta
import httpx
import os

from app.database import get_db
from app.models.user import User
from app.core.security import verify_password, get_password_hash, create_access_token
from app.utils.exceptions import UnauthorizedException, BadRequestException
from app.schemas.user import NaverCallbackRequest

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

# 네이버 로그인 (기존 회원용)
@router.post(
    "/naver/login",
    summary="네이버 로그인 (기존 회원)",
    operation_id="naver_login",
    description="기존 네이버 회원의 로그인을 처리합니다. 신규 가입은 /users/signup/naver 사용",
    response_model=TokenResponse,
)
async def naver_login(data: NaverCallbackRequest, db: Session = Depends(get_db)) -> TokenResponse:
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
            
            if not email:
                raise HTTPException(status_code=400, detail="이메일 정보를 가져올 수 없습니다")
            
            # 3. 기존 사용자 확인
            user = db.query(User).filter(User.email == email).first()
            
            if not user:
                raise HTTPException(
                    status_code=404, 
                    detail="가입되지 않은 사용자입니다. /users/signup/naver 에서 회원가입을 진행해주세요."
                )
            
            if user.signup_type != "naver":
                raise BadRequestException("네이버 로그인 회원이 아닙니다")
            
            # 4. JWT 토큰 발급
            access_token = create_access_token(
                {"sub": str(user.id)}, 
                expires_delta=timedelta(days=7)
            )
            
            return {"access_token": access_token, "token_type": "bearer"}
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"네이버 로그인 처리 중 오류: {str(e)}")
