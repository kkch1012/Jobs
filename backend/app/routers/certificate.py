from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.certificate import Certificate
from app.schemas.certificate import CertificateCreate, CertificateResponse
from app.core.security import admin_only
from app.models.user import User

router = APIRouter(prefix="/certificates", tags=["certificates"])

# 사용자용 자격증 전체 목록 조회 (선택 시 보여줄 용도)
@router.get(
    "/",
    response_model=list[CertificateResponse],
    summary="전체 자격증 목록 조회",
    description="""
모든 사용자가 선택할 수 있는 자격증 목록을 조회합니다.

- 이 목록은 관리자에 의해 미리 등록된 기준 자격증 리스트입니다.
- 회원가입 또는 이력서 작성 시 사용자가 선택할 수 있도록 제공합니다.
"""
)
def list_all_certificates(db: Session = Depends(get_db)):
    return db.query(Certificate).all()

# 기준 자격증 등록 (관리자만 가능)
@router.post(
    "/",
    response_model=CertificateResponse,
    summary="자격증 등록 (관리자 전용)",
    description="""
기준 자격증을 등록합니다. (관리자 전용)

- 자격증명과 발급기관을 입력받아 등록합니다.
- 등록된 자격증은 사용자들이 선택 가능한 기준 자격증으로 사용됩니다.
"""
)
def create_certificate(
    cert_data: CertificateCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(admin_only)
):
    new_cert = Certificate(name=cert_data.name, issuer=cert_data.issuer)
    db.add(new_cert)
    db.commit()
    db.refresh(new_cert)
    return new_cert

# 기준 자격증 삭제 (관리자만 가능)
@router.delete(
    "/{cert_id}",
    status_code=204,
    summary="자격증 삭제 (관리자 전용)",
    description="""
기준 자격증을 삭제합니다. (관리자 전용)

- `cert_id`는 삭제할 자격증의 고유 ID입니다.
- 해당 자격증이 존재하지 않을 경우 404 에러를 반환합니다.
- 삭제 시, 사용자와의 연결 기록은 유지되며 기준 리스트에서만 제거됩니다.
"""
)
def delete_certificate(
    cert_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(admin_only)
):
    cert = db.query(Certificate).filter(Certificate.id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="자격증을 찾을 수 없습니다.")
    db.delete(cert)
    db.commit()
    return Response(status_code=204)
