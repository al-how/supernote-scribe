"""Shared pytest fixtures for tests."""
from pathlib import Path

import pytest

from app.database import close_connection, init_db, set_db_path


@pytest.fixture
def test_db(tmp_path):
    """Set up test database."""
    db_path = tmp_path / "test.db"
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
