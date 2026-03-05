"""Shared pytest fixtures for tests."""
from pathlib import Path

import pytest

from app.config import Settings
from app.database import close_connection, init_db, set_db_path


@pytest.fixture
def test_db(tmp_path):
    """Set up test database."""
    db_path = tmp_path / "test.db"
    close_connection()  # Close any prior connection before switching DB path
    set_db_path(db_path)
    init_db()
    yield
    # Close connection to allow proper isolation between tests
    close_connection()


@pytest.fixture
def png_output_dir(tmp_path):
    """Temporary directory for PNG output."""
    output_dir = tmp_path / "png_cache"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def sample_note_path():
    """Path to a real .note fixture."""
    return Path("tests/fixtures/20251222_Note to Maggie.note")


@pytest.fixture
def work_note_path():
    """Path to a WORK .note fixture."""
    return Path("tests/fixtures/WORK/20250925_164518.note")


@pytest.fixture
def daily_note_path():
    """Path to a Daily Journal .note fixture."""
    return Path("tests/fixtures/Daily Journal/20260107_212138.note")


# OCR Service Fixtures

@pytest.fixture
def sample_png_path():
    """Path to a sample PNG for OCR testing."""
    return Path("tests/fixtures/sample_page.png")


@pytest.fixture
def mock_settings():
    """Mock Settings object for OCR testing."""
    return Settings(
        ollama_url="http://localhost:11434",
        ollama_model="qwen3-vl:8b",
        openai_api_key="sk-test-key",
        openai_model="gpt-4o",
        ocr_timeout=120,
    )


@pytest.fixture
def ollama_success_response():
    """Mock successful Ollama API response."""
    return {
        "model": "qwen3-vl:8b",
        "response": "This is extracted text from the handwritten note.",
        "done": True,
    }


@pytest.fixture
def openai_success_response():
    """Mock successful OpenAI API response."""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "This is extracted text from the handwritten note.",
                },
                "finish_reason": "stop",
            }
        ],
    }
