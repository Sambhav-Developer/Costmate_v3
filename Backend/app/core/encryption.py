import os
import base64

# Mock implementation since we don't have cryptography module setup yet
def encrypt_field(raw_value: str) -> str:
    if not raw_value:
        return raw_value
    return f"ENC:{base64.b64encode(raw_value.encode()).decode()}"

def decrypt_field(encrypted_value: str) -> str:
    if not encrypted_value or not str(encrypted_value).startswith("ENC:"):
        return encrypted_value
    try:
        raw_b64 = str(encrypted_value)[4:]
        return base64.b64decode(raw_b64).decode()
    except Exception:
        return encrypted_value
