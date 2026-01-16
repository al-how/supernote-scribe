"""Application configuration using Pydantic Settings.

Loads settings from environment variables and .env file.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    source_path: Path = Field(
        default=Path("/data/source"),
        description="Path to Supernote sync directory containing .note files",
    )
    output_path: Path = Field(
        default=Path("/data/output"),
        description="Path to Obsidian Journals output directory",
    )
    database_path: Path = Field(
        default=Path("data/supernote.db"),
        description="Path to SQLite database file",
    )
    png_cache_path: Path = Field(
        default=Path("data/png_cache"),
        description="Path to PNG cache directory",
    )

    # Ollama (primary OCR)
    ollama_url: str = Field(
        default="http://192.168.1.138:11434",
        description="Ollama server URL",
    )
    ollama_model: str = Field(
        default="qwen3-vl:8b",
        description="Ollama vision model for OCR",
    )

    # OpenAI (fallback OCR)
    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key for fallback OCR (None = not configured)",
    )
    openai_model: str = Field(
        default="gpt-4o",
        description="OpenAI model for fallback OCR",
    )

    # Processing thresholds
    quality_threshold: int = Field(
        default=50,
        ge=0,
        description="Minimum characters from primary OCR before triggering fallback",
    )
    auto_approve_threshold: int = Field(
        default=200,
        ge=0,
        description="Minimum characters for auto-approval (skip review queue)",
    )
    ocr_timeout: int = Field(
        default=120,
        ge=1,
        description="OCR request timeout in seconds",
    )

    # Scheduling
    # NOTE: Cron expression validation deferred - invalid expressions will fail
    # at runtime when the scheduler parses them, not at config load time.
    schedule_cron: str = Field(
        default="0 3 * * *",
        description="Cron expression for scheduled processing (default: 3am daily)",
    )
    schedule_enabled: bool = Field(
        default=False,
        description="Enable/disable scheduled processing",
    )


# Module-level singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get application settings (singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Force reload settings from environment."""
    global _settings
    _settings = Settings()
    return _settings


def init_app() -> Settings:
    """Initialize application: load settings and set up database."""
    from app.database import init_db, set_db_path

    settings = get_settings()
    set_db_path(settings.database_path)
    init_db()
    return settings
