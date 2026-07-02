from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SMALLERDOCS_", extra="ignore")

    temp_root: Path = Field(default=Path(os.getenv("TEMP", "/tmp")) / "smallerdocs")
    max_file_size_bytes: int = 50 * 1024 * 1024
    max_pages: int = 100
    job_ttl_minutes: int = 30
    cleanup_interval_seconds: int = 600
    page_concurrency: int = 4
    export_timeout_seconds: int = 45
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    native_pdf_min_words: int = 10


settings = Settings()
