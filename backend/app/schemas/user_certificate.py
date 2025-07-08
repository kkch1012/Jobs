from pydantic import BaseModel, Field
from datetime import date
from typing import Optional

class UserCertificateCreate(BaseModel):
    certificate_name: str = Field(..., description="자격증 이름") 
    acquired_date: date = Field(..., description="자격증 취득일")

class UserCertificateResponse(UserCertificateCreate):
    id: Optional[int] = None

    class Config:
        from_attributes = True
