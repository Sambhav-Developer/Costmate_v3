from datetime import datetime
import secrets
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from sqlalchemy.dialects.postgresql import insert
from app.db.postgres import hash_password
from app.models.user import User
from app.models.session import Session as DBSession, EmailVerification

class AuthRepository:
    def check_user_exists(self, db: Session, email: str) -> bool:
        stmt = select(User.id).where(User.email == email)
        return db.execute(stmt).scalar() is not None

    def upsert_email_verification(self, db: Session, email: str, password: str, otp: str, expires_at: datetime):
        pwd_hash, salt = hash_password(password)
        
        # PostgreSQL specific upsert
        stmt = insert(EmailVerification).values(
            email=email,
            password_hash=pwd_hash,
            salt=salt,
            otp=otp,
            expires_at=expires_at
        )
        
        do_update_stmt = stmt.on_conflict_do_update(
            index_elements=['email'],
            set_=dict(
                password_hash=stmt.excluded.password_hash,
                salt=stmt.excluded.salt,
                otp=stmt.excluded.otp,
                expires_at=stmt.excluded.expires_at
            )
        )
        db.execute(do_update_stmt)
        db.commit()

    def get_email_verification(self, db: Session, email: str):
        stmt = select(EmailVerification).where(EmailVerification.email == email)
        result = db.execute(stmt).scalar_one_or_none()
        if result:
            return (result.password_hash, result.salt, result.otp, result.expires_at)
        return None

    def create_user(self, db: Session, email: str, pwd_hash: str, salt: str) -> int:
        new_user = User(
            username=email,
            email=email,
            password_hash=pwd_hash,
            salt=salt
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user.id

    def delete_email_verification(self, db: Session, email: str):
        stmt = delete(EmailVerification).where(EmailVerification.email == email)
        db.execute(stmt)
        db.commit()

    def create_session(self, db: Session, user_id: int, expires_at: datetime) -> str:
        token = secrets.token_hex(32)
        new_session = DBSession(
            token=token,
            user_id=user_id,
            expires_at=expires_at
        )
        db.add(new_session)
        db.commit()
        return token

    def get_user_by_email(self, db: Session, email: str):
        stmt = select(User).where(User.email == email)
        result = db.execute(stmt).scalar_one_or_none()
        if result:
            return (result.id, result.password_hash, result.salt)
        return None

    def delete_session(self, db: Session, token: str):
        stmt = delete(DBSession).where(DBSession.token == token)
        db.execute(stmt)
        db.commit()

auth_repo = AuthRepository()
