from fastapi import APIRouter, Depends, Header, Query
from app.dependencies import get_db, get_current_user
from app.core.responses import success_response
from app.modules.auth import service
from app.modules.auth.schemas import (
    UserAuthSchema, GoogleAuthSchema, UserRegisterSchema, 
    UserVerifySchema, SignupResponseSchema, UserResponseSchema, 
    TokenResponseSchema
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])

@router.post("/signup")
async def signup(auth_data: UserRegisterSchema, conn = Depends(get_db)):
    result = await service.signup(conn, auth_data)
    return success_response(data=result, message="OTP sent")

@router.post("/verify-otp")
async def verify_otp(verify_data: UserVerifySchema, conn = Depends(get_db)):
    result = await service.verify_otp(conn, verify_data)
    return success_response(data=result, message="Email verified")

@router.post("/login")
async def login(auth_data: UserAuthSchema, conn = Depends(get_db)):
    result = await service.login(conn, auth_data)
    return success_response(data=result, message="Login successful")

@router.post("/logout")
async def logout(
    conn = Depends(get_db),
    authorization: str = Header(None),
    token: str = Query(None)
):
    resolved_token = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            resolved_token = parts[1]
    if not resolved_token and token:
        resolved_token = token
        
    result = await service.logout(conn, resolved_token)
    return success_response(data=result, message="Logged out")

@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return success_response(data=current_user, message="Current user fetched")

@router.get("/public-key")
async def get_public_key():
    from app.core.crypto_utils import get_server_rsa_public_key_pem
    try:
        public_key = get_server_rsa_public_key_pem()
        return success_response(data={"public_key": public_key}, message="RSA Public Key fetched")
    except Exception as e:
        return success_response(data=None, message=str(e))

@router.post("/google")
async def google_login(auth_data: GoogleAuthSchema, conn = Depends(get_db)):
    result = await service.google_login(conn, auth_data)
    return success_response(data=result, message="Google login successful")
