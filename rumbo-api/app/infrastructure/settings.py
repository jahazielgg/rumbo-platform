from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Rumbo API"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./rumbo.db"
    upload_dir: str = "./storage/uploads"
    cors_origins: str = "http://localhost:5173"
    max_upload_mb: int = 20
    seed_sample_data: bool = True
    structural_mapper_url: str = "http://structural-mapper:8010"
    structural_mapper_timeout_seconds: float = 120.0

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir).resolve()

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
