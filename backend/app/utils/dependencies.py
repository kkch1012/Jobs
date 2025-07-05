from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.models.user import User
from app.database import get_db
from sqlalchemy.orm import Session
from app.config import settings 

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# JWT 토큰에서 현재 사용자 가져오기
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="자격 증명이 유효하지 않습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        print("JWT payload:", payload)  # 토큰 디코딩 결과 확인
        user_id: int = int(payload.get("sub"))  # ← 이 값이 None이면 실패
        if user_id is None:
            print(" 'sub' not in payload")
            raise credentials_exception
    except JWTError as e:
        print(" JWT decode error:", e)
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        print("유저 ID로 조회 실패:", user_id)
        raise credentials_exception

    print("인증된 유저:", user.id, user.email)
    return user

