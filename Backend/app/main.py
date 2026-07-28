import sys
import os
# Add parent directory to sys.path to resolve Backend package imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.core.logging import logger
from app.modules.auth.router import router as auth_router
from app.modules.chat.router import router as chat_router
from app.modules.estimations.router import router as estimations_router
from app.db.postgres import init_db, close_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database
    init_db()
    
    banner = f"""
======================================================================
  _____          _                  _       
 / ____|        | |                | |      
| |     ___  ___| |_ _ __ ___   __ _| |_ ___ 
| |    / _ \\/ __| __| '_ ` _ \\ / _` | __/ _ \\
| |___| (_) \\__ \\ |_| | | | | | (_| | ||  __/
 \\_____\\___/|___/\\__|_| |_| |_|\\__,_|\\__\\___|
 
        🛠️  Civil Work Estimation Engine Backend Active 🛠️
======================================================================
  ├─ 🌐 Environment: {settings.APP_ENV}
  ├─ 🔌 Server URL: http://{settings.HOST if settings.HOST != "0.0.0.0" else "127.0.0.1"}:{settings.PORT}
  ├─ 🤖 LLM endpoint: {settings.OPENROUTER_BASE_URL}
  ├─ 🧠 Model name: {settings.MODEL_NAME}
  ├─ 📂 Upload Directory: {settings.UPLOAD_DIR}
  └─ 📁 Output Directory: {settings.OUTPUT_DIR}
======================================================================
"""
    logger.info(banner)
    yield
    # Close database pool on shutdown
    close_db()

# Initialize FastAPI application
app = FastAPI(
    title="Costmate API",
    description="AI-powered Construction Cost Estimation Engine API Backend",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS for Next.js Frontend compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, lock this down to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body = await request.body()
    logger.error(f"422 Error! Body: {body.decode('utf-8', errors='ignore')} | Errors: {exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors(), "body": body.decode('utf-8', errors='ignore')})

from app.middleware.auth import AuthMiddleware
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.request_logger import RequestLoggerMiddleware
from app.middleware.decryption_middleware import DecryptionMiddleware

# Note: The last middleware added is the FIRST one to execute
app.add_middleware(DecryptionMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(RateLimiterMiddleware)
app.add_middleware(RequestLoggerMiddleware)

# Serve uploads and output files statically for preview/access
app.mount("/static/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
app.mount("/static/output", StaticFiles(directory=settings.OUTPUT_DIR), name="output")

app.include_router(auth_router)
app.include_router(estimations_router)
app.include_router(chat_router)

from app.modules.estimations.v2_router import v2_router
app.include_router(v2_router)

# Startup logging handled by lifespan context manager

@app.get("/")
async def root():
    return {
        "app": "Costmate AI Engine Backend",
        "version": "0.1.0",
        "status": "healthy"
    }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.APP_ENV == "development"
    )
