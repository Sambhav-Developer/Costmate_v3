import time
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse

# Simple in-memory rate limiter
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW_SECONDS = 60
ip_requests = {}

class RateLimiterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        if client_ip not in ip_requests:
            ip_requests[client_ip] = []
            
        # Clean up old requests
        ip_requests[client_ip] = [req_time for req_time in ip_requests[client_ip] if current_time - req_time < RATE_LIMIT_WINDOW_SECONDS]
        
        if len(ip_requests[client_ip]) >= RATE_LIMIT_REQUESTS:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too Many Requests. Please try again later."}
            )
            
        ip_requests[client_ip].append(current_time)
        return await call_next(request)
