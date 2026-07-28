from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.models.base import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=True)
    email = Column(String(255), unique=True, index=True)
    password_hash = Column(String(255), nullable=True)
    salt = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
