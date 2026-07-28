from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.models.base import Base

class Session(Base):
    __tablename__ = "sessions"
    
    token = Column(String(255), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

class EmailVerification(Base):
    __tablename__ = "email_verifications"
    
    email = Column(String(255), primary_key=True)
    password_hash = Column(String(255), nullable=False)
    salt = Column(String(255), nullable=False)
    otp = Column(String(6), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
