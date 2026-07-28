import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # LLM Settings (OpenRouter)
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_API_KEY: str = ""
    MODEL_NAME: str = "qwen/qwen3.5-397b-a17b"

    # App settings
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Paths (relative to Backend/ folder)
    UPLOAD_DIR: str = "uploads"
    OUTPUT_DIR: str = "output"

    # PostgreSQL Database settings
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "costmate"

    # SMTP Settings
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_TLS: bool = True

    # Oauth settings 
    GOOGLE_CLIENT_ID: str = "772465759794-e6kohhje4pq0gdnsfc417vf8vt56bifl.apps.googleusercontent.com"

    # Cloudinary settings
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # Auto-initialize paths
    def model_post_init(self, __context) -> None:
        # __file__ is Backend/app/config.py -> Backend/app -> Backend
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not os.path.isabs(self.UPLOAD_DIR):
            self.UPLOAD_DIR = os.path.normpath(os.path.join(base_dir, self.UPLOAD_DIR))
        if not os.path.isabs(self.OUTPUT_DIR):
            self.OUTPUT_DIR = os.path.normpath(os.path.join(base_dir, self.OUTPUT_DIR))
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
