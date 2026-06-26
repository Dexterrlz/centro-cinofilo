from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/cinofilo"

    # Sicurezza
    SECRET_KEY: str = "chiave_segreta_da_cambiare"

    # Applicazione
    APP_NAME: str = "Centro Cinofilo"
    APP_URL: str = "http://localhost:8000"
    DEBUG: bool = False

    # Admin iniziale (solo primo avvio)
    ADMIN_INITIAL_USERNAME: Optional[str] = "admin"
    ADMIN_INITIAL_PASSWORD: Optional[str] = None


settings = Settings()
