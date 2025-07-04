from pydantic import BaseModel, Field

# 자격증 등록용 (관리자 또는 내부 등록)
class CertificateCreate(BaseModel):
    name: str = Field(..., description="자격증 이름")
    issuer: str = Field(..., description="발급 기관")

# 자격증 응답용 (사용자 조회용)
class CertificateResponse(BaseModel):
    id: int
    name: str
    issuer: str

    class Config:
        from_attributes = True
