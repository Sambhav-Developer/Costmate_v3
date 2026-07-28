import hashlib
import secrets
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.core.logging import logger
from app.models.base import Base
import app.models  # Ensures all models are registered with Base
from urllib.parse import quote_plus

# Construct SQLAlchemy connection string (using psycopg 3)
encoded_password = quote_plus(settings.POSTGRES_PASSWORD)
SQLALCHEMY_DATABASE_URL = (
    f"postgresql+psycopg://{settings.POSTGRES_USER}:{encoded_password}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)

logger.info("Creating SQLAlchemy engine...")
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    logger.info("Initializing PostgreSQL with SQLAlchemy...")
    try:
        # In a real production app, you would use Alembic to manage this.
        # But for now, we use create_all to ensure tables exist.
        Base.metadata.create_all(bind=engine)
        logger.info("PostgreSQL Database schema initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing PostgreSQL: {e}")
        raise e

def close_db():
    logger.info("Closing PostgreSQL Connection Pool (SQLAlchemy)...")
    engine.dispose()

# Notice that get_db_connection is removed. We use get_db dependency instead.

# Password Hashing & Salt utilities
def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000
    ).hex()
    return pw_hash, salt

def verify_password(password: str, password_hash: str, salt: str) -> bool:
    pw_hash, _ = hash_password(password, salt)
    return pw_hash == password_hash
