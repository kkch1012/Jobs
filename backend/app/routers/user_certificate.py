from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user_certificate import UserCertificate
from app.schemas.user_certificate import UserCertificateCreate, UserCertificateResponse
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.models.certificate import Certificate

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
