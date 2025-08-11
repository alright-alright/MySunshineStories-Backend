"""
Database and application configuration
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "LucianTales API"
    VERSION: str = "2.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # API Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Database settings
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DATABASE_URL: Optional[str] = None
    
    # JWT Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # AWS S3 Settings (optional)
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-west-2")
    AWS_S3_BUCKET: Optional[str] = os.getenv("AWS_S3_BUCKET")
    
    # OAuth Settings
    GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET")
    APPLE_CLIENT_ID: Optional[str] = os.getenv("APPLE_CLIENT_ID")
    APPLE_CLIENT_SECRET: Optional[str] = os.getenv("APPLE_CLIENT_SECRET")
    
    # Stripe Settings (for subscriptions)
    STRIPE_SECRET_KEY: Optional[str] = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_PUBLISHABLE_KEY: Optional[str] = os.getenv("STRIPE_PUBLISHABLE_KEY")
    STRIPE_WEBHOOK_SECRET: Optional[str] = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set database URL based on environment
        if not self.DATABASE_URL:
            if self.ENVIRONMENT == "production":
                # PostgreSQL for production
                db_user = os.getenv("DB_USER", "postgres")
                db_pass = os.getenv("DB_PASSWORD", "")
                db_host = os.getenv("DB_HOST", "localhost")
                db_port = os.getenv("DB_PORT", "5432")
                db_name = os.getenv("DB_NAME", "luciantales")
                self.DATABASE_URL = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
            else:
                # SQLite for development
                self.DATABASE_URL = "sqlite:///./luciantales.db"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()