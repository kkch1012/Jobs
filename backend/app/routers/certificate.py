from fastapi import APIRouter, Depends, HTTPException, Response, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.certificate import Certificate
from app.schemas.certificate import CertificateCreate, CertificateResponse
from app.utils.dependencies import get_current_user
from app.utils.logger import app_logger
from typing import List
from app.models.user import User
from sqlalchemy import or_

router = APIRouter(prefix="/certificates", tags=["certificates"])

@router.get(
    "/",
    response_model=List[CertificateResponse],
    summary="전체 자격증 조회",
    description="등록된 모든 자격증을 조회합니다."
)
def list_all_certificates(db: Session = Depends(get_db)):
    try:
        certificates = db.query(Certificate).all()
        app_logger.info(f"자격증 조회 완료: {len(certificates)}건")
        return certificates
    except Exception as e:
        app_logger.error(f"자격증 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"자격증 조회 중 오류가 발생했습니다: {str(e)}")

@router.get(
    "/search",
    response_model=List[CertificateResponse],
    summary="자격증 검색",
    description="자격증을 이름 또는 발급기관(issuer)으로 부분 문자열 검색합니다."
)
def search_certificates(
    query: str = Query(..., description="검색할 자격증명 또는 발급기관명"),
    limit: int = Query(10, ge=1, le=50, description="최대 반환 개수"),
    db: Session = Depends(get_db)
):
    try:
        if not query.strip():
            return []
        search_term = f"%{query.strip()}%"
        certificates = db.query(Certificate).filter(
            or_(
                Certificate.name.ilike(search_term),
                Certificate.issuer.ilike(search_term)
            )
        ).limit(limit).all()
        app_logger.info(f"자격증 검색 완료: {query} → {len(certificates)}건")
        return certificates
    except Exception as e:
        app_logger.error(f"자격증 검색 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"자격증 검색 중 오류가 발생했습니다: {str(e)}")

@router.post(
    "/",
    response_model=CertificateResponse,
    summary="새로운 자격증 등록",
    description="새로운 자격증을 등록합니다."
)
def create_certificate(
    certificate: CertificateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # 중복 체크
        existing_cert = db.query(Certificate).filter(
            Certificate.name == certificate.name,
            Certificate.issuer == certificate.issuer
        ).first()
        if existing_cert:
            raise HTTPException(status_code=400, detail="이미 등록된 자격증입니다.")
        
        db_certificate = Certificate(**certificate.dict())
        db.add(db_certificate)
        db.commit()
        db.refresh(db_certificate)
        
        app_logger.info(f"새로운 자격증 등록 완료: {db_certificate.name}")
        return db_certificate
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"자격증 등록 실패: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"자격증 등록 중 오류가 발생했습니다: {str(e)}")

@router.delete(
    "/{certificate_id}",
    summary="자격증 삭제",
    description="기존 자격증을 삭제합니다."
)
def delete_certificate(
    certificate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        certificate = db.query(Certificate).filter(Certificate.id == certificate_id).first()
        if not certificate:
            raise HTTPException(status_code=404, detail="자격증을 찾을 수 없습니다.")
        
        db.delete(certificate)
        db.commit()
        
        app_logger.info(f"자격증 삭제 완료: {certificate.name}")
        return {"message": "자격증이 성공적으로 삭제되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"자격증 삭제 실패: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"자격증 삭제 중 오류가 발생했습니다: {str(e)}")
