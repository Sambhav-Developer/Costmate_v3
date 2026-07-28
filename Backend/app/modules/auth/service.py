from datetime import datetime, timedelta, timezone
import secrets
import httpx
from app.modules.auth.repository import auth_repo
from app.modules.auth.schemas import UserRegisterSchema, UserVerifySchema, UserAuthSchema, GoogleAuthSchema
from app.core.exceptions import ValidationException, UnauthorizedException
from app.core.mail import send_otp_email
from app.core.logging import logger
from app.config import settings
from app.db.postgres import verify_password

async def signup(conn, auth_data: UserRegisterSchema):
    email = auth_data.email.strip()
    password = auth_data.password
    
    if not email or not password:
        raise ValidationException("Email and password cannot be empty")
        
    if auth_repo.check_user_exists(conn, email):
        raise ValidationException("Email is already registered")

    otp = f"{secrets.randbelow(900000) + 100000}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    
    auth_repo.upsert_email_verification(conn, email, password, otp, expires_at)
    conn.commit()
    
    try:
        send_otp_email(email, otp)
        logger.info(f"OTP verification code sent to {email}")
    except Exception as mail_err:
        logger.error(f"Failed to send SMTP email to {email}: {mail_err}")
        logger.warning("==================================================")
        logger.warning(f"  FALLBACK OTP FOR DEVELOPMENT: {otp}")
        logger.warning(f"  Please enter this code in the UI to register.")
        logger.warning("==================================================")
        
    return {"status": "otp_sent", "email": email}

async def verify_otp(conn, verify_data: UserVerifySchema):
    email = verify_data.email.strip()
    otp = verify_data.otp.strip()
    now = datetime.now(timezone.utc)
    
    row = auth_repo.get_email_verification(conn, email)
    if not row:
        raise ValidationException("No pending registration request found for this email. Please sign up again.")
    
    pwd_hash, salt, db_otp, expires_at = row
    
    if expires_at < now:
        raise ValidationException("Verification code has expired. Please sign up again to receive a new code.")
        
    if db_otp != otp:
        raise ValidationException("Invalid verification code.")
    
    user_id = auth_repo.create_user(conn, email, pwd_hash, salt)
    auth_repo.delete_email_verification(conn, email)
    
    session_expires = now + timedelta(days=7)
    token = auth_repo.create_session(conn, user_id, session_expires)
    conn.commit()
    
    logger.info(f"User email verified & registered successfully: {email} (ID: {user_id})")
    return {"access_token": token, "token_type": "bearer"}

async def login(conn, auth_data: UserAuthSchema):
    email = auth_data.email.strip()
    password = auth_data.password
    
    row = auth_repo.get_user_by_email(conn, email)
    if not row:
        raise UnauthorizedException("Incorrect email or password")
    
    user_id, pwd_hash, salt = row
    if not verify_password(password, pwd_hash, salt):
        raise UnauthorizedException("Incorrect email or password")
    
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    token = auth_repo.create_session(conn, user_id, expires_at)
    conn.commit()
    
    logger.info(f"User login successful: {email} (Session token created)")
    return {"access_token": token, "token_type": "bearer"}

async def logout(conn, token: str):
    auth_repo.delete_session(conn, token)
    conn.commit()
    return {"status": "success", "message": "Successfully logged out"}

async def google_login(conn, auth_data: GoogleAuthSchema):
    token_id = auth_data.id_token
    
    async with httpx.AsyncClient() as client:
        try:
            google_response = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": token_id}
            )
            if google_response.status_code != 200:
                raise UnauthorizedException("Invalid Google ID Token")
            user_info = google_response.json()
        except Exception as e:
            logger.error(f"Failed to verify Google token: {e}")
            raise UnauthorizedException("Google authentication failed")

    aud = user_info.get("aud")
    if aud != settings.GOOGLE_CLIENT_ID:
        raise UnauthorizedException("Audience mismatch. Invalid request origin.")

    email = user_info.get("email")
    if not email:
        raise ValidationException("Email not provided by Google account")
    email = email.strip()

    now = datetime.now(timezone.utc)
    
    row = auth_repo.get_user_by_email(conn, email)
    if row:
        user_id = row[0]
    else:
        user_id = auth_repo.create_user(conn, email, None, None)

    session_expires = now + timedelta(days=7)
    session_token = auth_repo.create_session(conn, user_id, session_expires)
    conn.commit()
    
    logger.info(f"Google OAuth login successful: {email} (ID: {user_id})")
    return {"access_token": session_token, "token_type": "bearer"}
