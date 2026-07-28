from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from sqlalchemy import select
from app.db.postgres import SessionLocal
from app.models.user import User
from app.models.session import Session as DBSession

PUBLIC_PATHS = [
    "/api/auth/login",
    "/api/auth/signup",
    "/api/auth/public-key",
    "/api/auth/verify-otp",
    "/api/auth/resend-otp",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/static",
    "/"
]

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip auth for public paths
        for path in PUBLIC_PATHS:
            if request.url.path.startswith(path) or request.url.path == "/":
                return await call_next(request)

        # Allow OPTIONS requests for CORS
        if request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing or invalid Authorization header"})
            
        token = auth_header.split(" ")[1]
        
        now = datetime.now(timezone.utc)
        try:
            db = SessionLocal()
            try:
                stmt = (
                    select(User.id)
                    .join(DBSession, DBSession.user_id == User.id)
                    .where(DBSession.token == token)
                    .where(DBSession.expires_at > now)
                )
                user_id = db.execute(stmt).scalar_one_or_none()
                if not user_id:
                    return JSONResponse(status_code=401, content={"detail": "Invalid or expired session token"})
            finally:
                db.close()
        except Exception as e:
            return JSONResponse(status_code=500, content={"detail": f"Database error during authentication: {e}"})
            
        return await call_next(request)
