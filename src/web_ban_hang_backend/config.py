from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    DB_URL: str
    FIREBASE_CREDENTIALS_PATH: str
    FIREBASE_CREDENTIALS_JSON: Optional[str] = None
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "https://web-ban-hang-blue.vercel.app"]
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings() # pyright: ignore[reportCallIssue]