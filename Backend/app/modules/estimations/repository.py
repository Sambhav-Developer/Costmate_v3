from typing import List, Optional
import json
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from app.models.estimation import EstimationSession, DraftEstimationSession, InPlatformNotification

class EstimationRepository:
    def get_user_sessions(self, db: Session, user_id: int) -> List[tuple]:
        stmt = (
            select(EstimationSession.id, EstimationSession.state, EstimationSession.created_at)
            .where(EstimationSession.user_id == user_id)
            .order_by(EstimationSession.updated_at.desc())
        )
        result = db.execute(stmt).all()
        return [(row.id, row.state, row.created_at) for row in result]

    def get_draft_session(self, db: Session, session_id: str, user_id: int) -> tuple:
        stmt = (
            select(
                DraftEstimationSession.project_name, 
                DraftEstimationSession.swarm_goal, 
                DraftEstimationSession.rate_schedule, 
                DraftEstimationSession.uploaded_file_path, 
                DraftEstimationSession.original_filename, 
                DraftEstimationSession.uploaded_page_paths, 
                DraftEstimationSession.status
            )
            .where(DraftEstimationSession.id == session_id, DraftEstimationSession.user_id == user_id)
        )
        result = db.execute(stmt).first()
        if result:
            return (
                result.project_name, 
                result.swarm_goal, 
                result.rate_schedule, 
                result.uploaded_file_path, 
                result.original_filename, 
                result.uploaded_page_paths, 
                result.status
            )
        return None

    def create_draft_session(self, db: Session, session_id: str, user_id: int, req) -> None:
        new_draft = DraftEstimationSession(
            id=session_id,
            user_id=user_id,
            project_name=req.project_name,
            swarm_goal=req.swarm_goal,
            rate_schedule=req.rate_schedule
        )
        db.add(new_draft)
        db.commit()

    def update_draft_session_file(self, db: Session, session_id: str, user_id: int, file_path: str, orig_name: str, page_paths: list) -> None:
        stmt = (
            update(DraftEstimationSession)
            .where(DraftEstimationSession.id == session_id, DraftEstimationSession.user_id == user_id)
            .values(
                uploaded_file_path=file_path,
                original_filename=orig_name,
                uploaded_page_paths=page_paths,
                status='file_uploaded'
            )
        )
        db.execute(stmt)
        db.commit()

    def mark_draft_complete(self, db: Session, session_id: str, user_id: int) -> None:
        stmt = (
            update(DraftEstimationSession)
            .where(DraftEstimationSession.id == session_id, DraftEstimationSession.user_id == user_id)
            .values(status='completed')
        )
        db.execute(stmt)
        db.commit()

    def delete_session(self, db: Session, session_id: str, user_id: int) -> None:
        stmt = (
            delete(EstimationSession)
            .where(EstimationSession.id == session_id, EstimationSession.user_id == user_id)
        )
        db.execute(stmt)
        db.commit()

    def get_notifications(self, db: Session, session_id: str, user_id: int) -> List[tuple]:
        stmt = (
            select(InPlatformNotification.id, InPlatformNotification.message, InPlatformNotification.type, InPlatformNotification.is_read, InPlatformNotification.created_at)
            .where(InPlatformNotification.user_id == user_id)
            .order_by(InPlatformNotification.created_at.desc())
        )
        result = db.execute(stmt).all()
        return [(row.id, row.message, row.type, row.is_read, row.created_at) for row in result]

    def create_notification(self, db: Session, user_id: int, message: str, type: str) -> int:
        new_notification = InPlatformNotification(
            user_id=user_id,
            message=message,
            type=type
        )
        db.add(new_notification)
        db.commit()
        db.refresh(new_notification)
        return new_notification.id

    def mark_notification_read(self, db: Session, notification_id: int, user_id: int) -> None:
        stmt = (
            update(InPlatformNotification)
            .where(InPlatformNotification.id == notification_id, InPlatformNotification.user_id == user_id)
            .values(is_read=True)
        )
        db.execute(stmt)
        db.commit()

estimation_repo = EstimationRepository()
