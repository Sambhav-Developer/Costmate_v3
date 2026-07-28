import json
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from app.core.crypto_utils import decrypt_aes_key_with_rsa, decrypt_payload_with_aes_gcm, encrypt_payload_with_aes_gcm

class DecryptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_aes_key = None
        
        # 1. Try to extract AES key from headers (especially for GET requests)
        if "x-encryption-key" in request.headers:
            try:
                client_aes_key = decrypt_aes_key_with_rsa(request.headers["x-encryption-key"])
            except Exception as e:
                print(f"[Middleware] Header key decryption failed: {e}")

        # 2. Intercept Request Body
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body_bytes = await request.body()
                if body_bytes:
                    body_json = json.loads(body_bytes)
                    if "rsa_encrypted_aes_key" in body_json and "aes_encrypted_payload" in body_json:
                        # Decrypt it
                        aes_key = decrypt_aes_key_with_rsa(body_json["rsa_encrypted_aes_key"])
                        client_aes_key = aes_key # Save for response encryption
                        decrypted_dict = decrypt_payload_with_aes_gcm(body_json["aes_encrypted_payload"], aes_key)
                        
                        new_body = json.dumps(decrypted_dict).encode("utf-8")
                        async def receive():
                            return {"type": "http.request", "body": new_body}
                        request._receive = receive
                        request._body = new_body
                    else:
                        async def receive():
                            return {"type": "http.request", "body": body_bytes}
                        request._receive = receive
                        request._body = body_bytes
            except Exception as e:
                async def receive():
                    return {"type": "http.request", "body": body_bytes}
                request._receive = receive
                request._body = body_bytes
                
        # 3. Call the actual route
        response = await call_next(request)
        
        # 4. Intercept Response Body and Encrypt if applicable
        if client_aes_key and response.headers.get("content-type") == "application/json":
            try:
                body_chunks = [chunk async for chunk in response.body_iterator]
                original_body = b"".join(body_chunks)
                
                json_data = json.loads(original_body)
                encrypted_b64 = encrypt_payload_with_aes_gcm(json_data, client_aes_key)
                
                # Replace response with encrypted string
                encrypted_response = JSONResponse(content={"encrypted_response": encrypted_b64}, status_code=response.status_code)
                for k, v in response.headers.items():
                    if k.lower() not in ["content-length", "content-type"]:
                        encrypted_response.headers[k] = v
                return encrypted_response
            except Exception as e:
                print(f"[Middleware] Response encryption failed: {e}")
                # Fallback to original body if encryption fails (e.g., non-JSON body)
                if 'original_body' in locals():
                    return Response(content=original_body, status_code=response.status_code, headers=dict(response.headers), media_type="application/json")

        return response
