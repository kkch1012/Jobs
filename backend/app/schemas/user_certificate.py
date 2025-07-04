from pydantic import BaseModel, Field
from datetime import date

class UserCertificateBase(BaseModel):
    certificate_id: int = Field(..., description="연결할 자격증 ID")
    acquired_date: date = Field(..., description="자격증 취득일")

class UserCertificateCreate(UserCertificateBase):
    pass

class UserCertificateResponse(UserCertificateBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True
