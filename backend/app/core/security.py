from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from app.config import settings
from app.utils.dependencies import get_current_user
from app.models.user import User

# 비밀번호 해싱에 사용할 bcrypt 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 평문 비밀번호와 해시된 비밀번호 검증
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# 비밀번호 해싱
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# 액세스 토큰 생성
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# 관리자 권한 체크 (현재 User 모델에 role 필드가 없으므로 주석 처리)
# def admin_only(current_user: User = Depends(get_current_user)):
#     if getattr(current_user, 'role', None) != "admin":
#         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다.")
#     return current_user
