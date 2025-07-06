from pydantic import BaseModel, Field
from datetime import date

class UserCertificateCreate(BaseModel):
    certificate_name: str = Field(..., description="자격증 이름") 
    acquired_date: date = Field(..., description="자격증 취득일")

class UserCertificateResponse(BaseModel):
    id: int
    user_id: int
    certificate_id: int
    acquired_date: date

    class Config:
        orm_mode = True
