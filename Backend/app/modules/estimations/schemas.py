from pydantic import BaseModel
from typing import Optional

class DraftSessionRequest(BaseModel):
    project_name: str

class NotificationRequest(BaseModel):
    message: str
    type: str = "info"

class CompleteSessionRequest(BaseModel):
    intake_data: Optional[dict] = None

class EncryptedPayloadSchema(BaseModel):
    rsa_encrypted_aes_key: str
    aes_encrypted_payload: str
