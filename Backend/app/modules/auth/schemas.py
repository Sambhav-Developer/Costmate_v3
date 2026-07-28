from pydantic import BaseModel

class UserAuthSchema(BaseModel):
    email: str
    password: str

class GoogleAuthSchema(BaseModel):
    id_token: str

class UserRegisterSchema(BaseModel):
    email: str
    password: str

class UserVerifySchema(BaseModel):
    email: str
    otp: str

class SignupResponseSchema(BaseModel):
    status: str
    email: str

class UserResponseSchema(BaseModel):
    id: int
    email: str
    created_at: str

class TokenResponseSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"
