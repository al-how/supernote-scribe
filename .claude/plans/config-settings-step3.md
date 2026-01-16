# Plan: Implement Config & Settings Layer (Step 3)

## Objective
Implement `app/config.py` with Pydantic Settings v2 for environment variable and `.env` file handling.

## Files to Create/Modify
- **Create:** `app/config.py` - Main settings module
- **Update:** `.env.example` - Add all environment variables with documentation

## Implementation Design

### 1. Settings Class (`app/config.py`)

```python
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore unknown env vars
    )

    # Paths
    source_path: Path = Field(
        default=Path("/data/source"),
        description="Path to Supernote sync directory containing .note files"
    )
    output_path: Path = Field(
        default=Path("/data/output"),
        description="Path to Obsidian Journals output directory"
    )
    database_path: Path = Field(
        default=Path("data/supernote.db"),
        description="Path to SQLite database file"
    )
    png_cache_path: Path = Field(
        default=Path("data/png_cache"),
        description="Path to PNG cache directory"
    )

    # Ollama (primary OCR)
    ollama_url: str = Field(
        default="http://192.168.1.138:11434",
        description="Ollama server URL"
    )
    ollama_model: str = Field(
        default="qwen3-vl:8b",
        description="Ollama vision model for OCR"
    )

    # OpenAI (fallback OCR)
    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key for fallback OCR (None = not configured)"
    )
    openai_model: str = Field(
        default="gpt-4o",
        description="OpenAI model for fallback OCR"
    )

    # Processing thresholds
    quality_threshold: int = Field(
        default=50,
        description="Minimum characters from primary OCR before triggering fallback"
    )
    auto_approve_threshold: int = Field(
        default=200,
        description="Minimum characters for auto-approval (skip review queue)"
    )
    ocr_timeout: int = Field(
        default=120,
        description="OCR request timeout in seconds"
    )

    # Scheduling
    schedule_cron: str = Field(
        default="0 3 * * *",
        description="Cron expression for scheduled processing (default: 3am daily)"
    )
    schedule_enabled: bool = Field(
        default=False,
        description="Enable/disable scheduled processing"
    )
```

### 2. Module-Level Access Pattern

Following the database.py pattern, provide module-level functions for singleton access:

```python
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
```

### 3. Integration with Database Layer

Add a helper function to initialize both config and database:

```python
def init_app() -> Settings:
    """Initialize application: load settings and set up database."""
    from app.database import set_db_path, init_db

    settings = get_settings()
    set_db_path(settings.database_path)
    init_db()
    return settings
```

### 4. Update `.env.example`

```env
# OpenAI (fallback OCR) - leave empty if not using OpenAI fallback
OPENAI_API_KEY=

# Ollama (primary OCR)
OLLAMA_URL=http://192.168.1.138:11434
OLLAMA_MODEL=qwen3-vl:8b

# Paths (override for local development)
SOURCE_PATH=/data/source
OUTPUT_PATH=/data/output
DATABASE_PATH=data/supernote.db
PNG_CACHE_PATH=data/png_cache

# Processing thresholds
QUALITY_THRESHOLD=50
AUTO_APPROVE_THRESHOLD=200
OCR_TIMEOUT=120

# Scheduling
SCHEDULE_CRON=0 3 * * *
SCHEDULE_ENABLED=false
```

## Implementation Steps

1. **Create `app/config.py`**
   - Import pydantic and pydantic-settings
   - Define `Settings` class with all fields and defaults
   - Add module-level `get_settings()` and `reload_settings()` functions
   - Add `init_app()` helper for startup initialization

2. **Update `.env.example`**
   - Add all environment variables with comments
   - Keep OPENAI_API_KEY first (as it's the only truly required secret)

3. **Verify integration**
   - Test that settings load from environment variables
   - Test that `.env` file is read correctly
   - Verify database integration via `init_app()`

## Verification

```python
# Test in Python REPL or simple script
from app.config import get_settings, init_app

# Check settings load correctly
settings = get_settings()
print(f"Source: {settings.source_path}")
print(f"Ollama: {settings.ollama_url}")

# Check database integration
init_app()  # Should initialize both config and database
```

## Notes

- Pydantic Settings v2 automatically handles type coercion (e.g., string to Path)
- Environment variables override `.env` file values
- The `extra="ignore"` setting prevents errors from unknown env vars
- Singleton pattern ensures settings are loaded once per process
