import base64
import json
import os
from pathlib import Path
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Hash import SHA256
from Crypto.Util.Padding import unpad
from Crypto.Random import get_random_bytes
from fastapi import HTTPException
from typing import Dict, Any

# Algorithm Constants
AES_ALGORITHM = 'aes-256-gcm'
AES_KEY_BYTE_LENGTH = 32  # 256 bits
IV_BYTE_LENGTH = 12       # 96 bits for GCM
AUTH_TAG_BYTE_LENGTH = 16  # 128 bits for GCM

# Paths (Adjust based on your setup)
SECURE_DIR = Path("secure")
PRIVATE_KEY_PATH = SECURE_DIR / "private_key.pem"
PUBLIC_KEY_PATH = SECURE_DIR / "public_key.pem"

def load_rsa_keys():
    """Load RSA keys or generate if missing for development."""
    if not PRIVATE_KEY_PATH.exists():
        print("[CryptoUtils] RSA Keys not found. Generating new ones...")
        key = RSA.generate(2048)
        private_key = key.export_key()
        public_key = key.publickey().export_key()
        
        SECURE_DIR.mkdir(exist_ok=True)
        with open(PRIVATE_KEY_PATH, "wb") as f:
            f.write(private_key)
        with open(PUBLIC_KEY_PATH, "wb") as f:
            f.write(public_key)
        print("[CryptoUtils] RSA Keys generated successfully.")

def get_server_rsa_public_key_pem() -> str:
    """Returns the RSA Public Key PEM content."""
    if not PUBLIC_KEY_PATH.exists():
        load_rsa_keys()
    with open(PUBLIC_KEY_PATH, "r") as f:
        return f.read()

def decrypt_aes_key_with_rsa(rsa_encrypted_base64_aes_key_b64: str) -> bytes:
    """Decrypts an RSA-OAEP encrypted AES key."""
    try:
        if not PRIVATE_KEY_PATH.exists():
            raise HTTPException(status_code=500, detail="Server RSA private key not found.")
        
        with open(PRIVATE_KEY_PATH, "r") as f:
            private_key = RSA.import_key(f.read())
        
        # RSA-OAEP with SHA-256
        cipher_rsa = PKCS1_OAEP.new(private_key, hashAlgo=SHA256)
        
        encrypted_bytes = base64.b64decode(rsa_encrypted_base64_aes_key_b64)
        decrypted_base64_key = cipher_rsa.decrypt(encrypted_bytes).decode('utf-8')
        
        aes_key_buffer = base64.b64decode(decrypted_base64_key)
        
        if len(aes_key_buffer) != AES_KEY_BYTE_LENGTH:
            raise ValueError(f"Decrypted AES key has incorrect length: {len(aes_key_buffer)}")
            
        return aes_key_buffer
    except Exception as e:
        print(f"[CryptoUtils] RSA Decryption Error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to decrypt AES key: {str(e)}")

def decrypt_payload_with_aes_gcm(aes_encrypted_payload_b64: str, aes_key_bytes: bytes) -> Dict[str, Any]:
    """Decrypts a payload using AES-256-GCM (IV + Ciphertext + AuthTag)."""
    try:
        combined_buffer = base64.b64decode(aes_encrypted_payload_b64)
        
        if len(combined_buffer) < (IV_BYTE_LENGTH + AUTH_TAG_BYTE_LENGTH):
            raise ValueError("Payload too short.")

        iv = combined_buffer[:IV_BYTE_LENGTH]
        auth_tag = combined_buffer[-AUTH_TAG_BYTE_LENGTH:]
        ciphertext = combined_buffer[IV_BYTE_LENGTH:-AUTH_TAG_BYTE_LENGTH]

        cipher = AES.new(aes_key_bytes, AES.MODE_GCM, nonce=iv)
        decrypted_json_string = cipher.decrypt_and_verify(ciphertext, auth_tag).decode('utf-8')
        
        return json.loads(decrypted_json_string)
    except Exception as e:
        print(f"[CryptoUtils] AES Decryption Error: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to decrypt or parse AES payload.")

def encrypt_payload_with_aes_gcm(payload: Dict[str, Any], aes_key_bytes: bytes) -> str:
    """Encrypts a payload using AES-256-GCM and returns base64 encoded IV + Ciphertext + AuthTag."""
    try:
        payload_bytes = json.dumps(payload).encode('utf-8')
        nonce = get_random_bytes(IV_BYTE_LENGTH)
        cipher = AES.new(aes_key_bytes, AES.MODE_GCM, nonce=nonce)
        ciphertext, auth_tag = cipher.encrypt_and_digest(payload_bytes)
        
        combined_buffer = nonce + ciphertext + auth_tag
        return base64.b64encode(combined_buffer).decode('utf-8')
    except Exception as e:
        print(f"[CryptoUtils] AES Encryption Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to encrypt payload.")
