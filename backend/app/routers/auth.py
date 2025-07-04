# 인증 관련 엔드포인트( 로그인, 회원가입 등 )

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.core.security import verify_password, get_password_hash, create_access_token

router = APIRouter(prefix="/auth",tags=["auth"])

# 토큰 응답 스키마 정의
class TokenResponse(BaseModel):
    access_token: str
    token_type: str

@router.post(
    "/login",
    summary="로그인 요청",
    description="""
사용자가 이메일과 비밀번호를 입력하여 로그인을 수행합니다.

- OAuth2PasswordRequestForm을 기반으로 이메일(username)과 비밀번호를 전달받습니다.
- 비밀번호가 맞을 경우 JWT 토큰을 발급하고 반환합니다.
- 토큰은 이후 인증이 필요한 요청에서 사용됩니다.

주의: 이메일 또는 비밀번호가 일치하지 않으면 401 에러를 반환합니다.
""",
    response_model=TokenResponse,
)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2PasswordRequestForm의 username 필드를 이메일로 사용
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    # 액세스 토큰 생성 및 반환
    access_token = create_access_token({"user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}
