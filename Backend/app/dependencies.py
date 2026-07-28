from datetime import datetime, timezone
from fastapi import Header, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.postgres import SessionLocal
from app.models.user import User
from app.models.session import Session as DBSession

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    authorization: str = Header(None),
    token: str = Query(None)
) -> dict:
    resolved_token = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            resolved_token = parts[1]
            
    if not resolved_token and token:
        resolved_token = token
        
    if not resolved_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing. Please provide it in Authorization header or token query parameter.",
        )
        
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        stmt = (
            select(User)
            .join(DBSession, DBSession.user_id == User.id)
            .where(DBSession.token == resolved_token)
            .where(DBSession.expires_at > now)
        )
        user = db.execute(stmt).scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session token",
            )
        return {
            "id": user.id,
            "email": user.email if user.email else "",
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
    finally:
        db.close()
