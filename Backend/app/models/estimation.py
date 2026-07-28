from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.sql import func
from app.models.base import Base

class EstimationSession(Base):
    __tablename__ = "estimation_sessions"
    
    id = Column(String(255), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    state = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class DraftEstimationSession(Base):
    __tablename__ = "draft_estimation_sessions"
    
    id = Column(String(255), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_name = Column(String(255), nullable=False)
    swarm_goal = Column(String(100), nullable=False)
    rate_schedule = Column(String(100), nullable=False)
    uploaded_file_path = Column(String(500), nullable=True)
    original_filename = Column(String(255), nullable=True)
    uploaded_page_paths = Column(ARRAY(String), nullable=True)
    status = Column(String(50), default='draft')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class InPlatformNotification(Base):
    __tablename__ = "in_platform_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    message = Column(String, nullable=False)
    type = Column(String(50), nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
