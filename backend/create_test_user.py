import sys
import os
from datetime import date
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

def create_test_user():
    """테스트용 사용자 계정 생성"""
    db = SessionLocal()
    try:
        # 기존 사용자 확인
        existing_user = db.query(User).filter(User.email == "user@example.com").first()
        if existing_user:
            print(" 테스트 사용자가 이미 존재합니다.")
            print(f"   ID: {existing_user.id}")
            print(f"   이메일: {existing_user.email}")
            print(f"   닉네임: {existing_user.nickname}")
            return existing_user
        
        # 새 사용자 생성
        test_user = User(
            email="user@example.com",
            hashed_password=get_password_hash("strongpassword"),
            nickname="testuser",
            name="테스트 사용자",
            phone_number="010-1234-5678",
            birth_date=date(1990, 1, 1),
            gender="남성",
            signup_type="id",
            university="테스트 대학교",
            major="컴퓨터공학과",
            gpa=3.5,
            education_status="졸업",
            degree="학사",
            desired_job="백엔드 개발자"
        )
        
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        print("✅ 테스트 사용자 생성 완료")
        print(f"   ID: {test_user.id}")
        print(f"   이메일: {test_user.email}")
        print(f"   닉네임: {test_user.nickname}")
        print(f"   비밀번호: strongpassword")
        
        return test_user
        
    except Exception as e:
        print(f"❌ 사용자 생성 실패: {e}")
        db.rollback()
        return None
    finally:
        db.close()

if __name__ == "__main__":
    create_test_user() 