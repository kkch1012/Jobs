from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user_certificate import UserCertificate
from app.schemas.user_certificate import UserCertificateCreate, UserCertificateResponse
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.models.certificate import Certificate
import re
from datetime import date

router = APIRouter(prefix="/users/me/certificates", tags=["UserCertificate"])



@router.post("/",
              response_model=UserCertificateResponse, 
              operation_id="add_user_certificate",
              summary="자격증 추가")
def add_user_certificate(
    data: UserCertificateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cert_master = db.query(Certificate).filter(Certificate.name == data.certificate_name).first()
    if not cert_master:
        raise HTTPException(status_code=404, detail="자격증을 찾을 수 없습니다.")

    user_cert = UserCertificate(
        user_id=getattr(current_user, 'id'),
        certificate_id=getattr(cert_master, 'id'),
        acquired_date=data.acquired_date
    )
    db.add(user_cert)
    db.commit()
    db.refresh(user_cert)
    
    # 응답 스키마에 맞춰 certificate_name 추가해서 반환
    return UserCertificateResponse(
        id=getattr(user_cert, 'id'),
        certificate_name=getattr(cert_master, 'name'),
        acquired_date=getattr(user_cert, 'acquired_date')
    )

@router.get("/", 
            response_model=List[UserCertificateResponse], 
            operation_id="get_my_certificates",
            summary="자격증 목록", description="""
로그인된 사용자가 보유한 자격증 목록을 조회합니다.

- 인증된 사용자만 접근 가능합니다.
""")
def get_my_certificates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_certs = (
        db.query(UserCertificate, Certificate.name.label("certificate_name"))
          .join(Certificate, UserCertificate.certificate_id == Certificate.id)
          .filter(UserCertificate.user_id == current_user.id)
          .all()
    )
    return [
        UserCertificateResponse(
            id=getattr(user_cert, 'id'),
            certificate_name=certificate_name,
            acquired_date=getattr(user_cert, 'acquired_date')
        )
        for user_cert, certificate_name in user_certs
    ]

@router.delete("/{cert_id}", 
               status_code=204, 
               operation_id="delete_user_certificate",
               summary="자격증 삭제", description="""
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

@router.post("/smart-add", 
             summary="스마트 자격증 추가", 
             operation_id="smart_add_user_certificate",
             description="""
사용자의 이력서에 자격증을 추가합니다.
- 중복 검사 기능
- `certificate_name`: 자격증 이름
- `acquired_date`: 취득일 (선택사항)
- 인증된 사용자만 사용할 수 있습니다.
""")
def smart_add_user_certificate(
    cert_data: dict,  # UserCertificateCreate에서 dict로 변경
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # dict에서 데이터 추출
    certificate_name = cert_data.get("certificate_name")
    acquired_date_str = cert_data.get("acquired_date")
    
    if not certificate_name:
        return {
            "status": "error",
            "message": "자격증명을 입력해주세요."
        }
    
    # 자격증 찾기
    certificate = db.query(Certificate).filter(Certificate.name == certificate_name).first()
    if not certificate:
        return {
            "status": "certificate_not_found",
            "message": f"'{certificate_name}' 자격증을 찾을 수 없습니다. 정확한 자격증명을 입력해주세요."
        }
    
    # 해당 유저가 이미 같은 자격증을 등록했는지 확인
    existing_user_cert = (
        db.query(UserCertificate)
          .filter(UserCertificate.user_id == current_user.id, UserCertificate.certificate_id == certificate.id)
          .first()
    )
    
    if existing_user_cert:
        return {
            "status": "duplicate",
            "message": f"이미 '{certificate.name}' 자격증이 등록되어 있습니다.",
            "certificate_name": certificate.name
        }
    
    # 취득일이 없으면 입력 요청
    if not acquired_date_str or acquired_date_str.strip() == "":
        return {
            "status": "need_acquired_date",
            "message": f"'{certificate.name}' 자격증의 취득일을 입력해주세요. (예: 2024-01-15, 또는 오늘)",
            "certificate_name": certificate.name,
            "certificate_id": certificate.id
        }
    
    # 취득일 파싱
    try:
        if acquired_date_str.lower() in ["오늘", "today"]:
            acquired_date = date.today()
        else:
            # YYYY-MM-DD 형식으로 파싱
            acquired_date = date.fromisoformat(acquired_date_str)
    except ValueError:
        return {
            "status": "invalid_date",
            "message": f"잘못된 날짜 형식입니다. YYYY-MM-DD 형식으로 입력해주세요. (예: 2024-01-15)",
            "certificate_name": certificate.name
        }
    
    # 새 UserCertificate 생성 및 저장
    user_cert = UserCertificate(
        user_id=current_user.id,
        certificate_id=certificate.id,
        acquired_date=acquired_date
    )
    db.add(user_cert)
    db.commit()
    db.refresh(user_cert)

    return {
        "status": "success",
        "message": f"'{certificate.name}' 자격증이 성공적으로 추가되었습니다.",
        "certificate_name": certificate.name,
        "acquired_date": str(acquired_date)
    }


