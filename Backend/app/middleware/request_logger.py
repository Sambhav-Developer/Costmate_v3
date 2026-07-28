import time
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from app.core.logging import logger

class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        client_host = request.client.host if request.client else "unknown"
        client_port = request.client.port if request.client else 0
        http_version = request.scope.get('http_version', '1.1')
        
        logger.info(f"{client_host}:{client_port} - \"{request.method} {request.url.path} HTTP/{http_version}\" {response.status_code} {process_time:.4f}s")
        return response
