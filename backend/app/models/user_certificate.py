from sqlalchemy import Column, Integer, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.database.PostgreSQL import Base

class UserCertificate(Base):
    __tablename__ = "user_certificates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    certificate_id = Column(Integer, ForeignKey("certificates.id", ondelete="CASCADE"))
    acquired_date = Column(Date, nullable=False)

    user = relationship("User", back_populates="certificates")
    certificate = relationship("Certificate", back_populates="users")
