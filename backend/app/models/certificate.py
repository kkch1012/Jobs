from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database.PostgreSQL import Base

class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, index=True)  
    name = Column(String, nullable=False)                
    issuer = Column(String, nullable=False)                  

    users = relationship("UserCertificate", back_populates="certificate", cascade="all, delete-orphan")
