"""Tests for scanner service."""
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from app.database import (
    get_note_by_path,
    init_db,
    set_db_path,
)
from app.services.scanner import (
    calculate_file_hash,
    extract_date_from_filename,
    get_note_date,
    scan_and_insert,
    scan_source_directory,
)


# =============================================================================
# Date Extraction Tests
# =============================================================================


def test_extract_date_standard_format():
    """Test YYYYMMDD_HHMMSS.note format."""
    assert extract_date_from_filename("20260107_212138.note") == date(2026, 1, 7)


def test_extract_date_with_description():
    """Test YYYYMMDD_Description.note format."""
    assert extract_date_from_filename("20251222_Note to Maggie.note") == date(
        2025, 12, 22
    )


def test_extract_date_no_date_prefix_returns_none():
    """Test filename without date prefix returns None (use mtime fallback)."""
    assert extract_date_from_filename("Florida.note") is None
    assert extract_date_from_filename("Meeting Notes.note") is None
    assert extract_date_from_filename("abc.note") is None


def test_extract_date_invalid_date_returns_none():
    """Test invalid date returns None (e.g., month 13)."""
    assert extract_date_from_filename("20261301_test.note") is None


def test_extract_date_short_filename():
    """Test filename shorter than 8 chars returns None."""
    assert extract_date_from_filename("abc.note") is None
    assert extract_date_from_filename("1.note") is None


# =============================================================================
# Note Date (with mtime fallback) Tests
# =============================================================================


def test_get_note_date_uses_filename_when_available(tmp_path):
    """Test that files with date prefix use filename date."""
    note = tmp_path / "20260107_212138.note"
    note.write_bytes(b"test")

    result = get_note_date(note)
    assert result == date(2026, 1, 7)


def test_get_note_date_uses_mtime_fallback(tmp_path):
    """Test that files without date prefix use file mtime."""
    note = tmp_path / "Florida.note"
    note.write_bytes(b"test")

    result = get_note_date(note)
    assert result == date.today()  # mtime is now


# =============================================================================
# File Hash Tests
# =============================================================================


def test_calculate_file_hash(tmp_path):
    """Test MD5 hash calculation."""
    note = tmp_path / "test.note"
    note.write_bytes(b"test content")

    hash1 = calculate_file_hash(note)
    assert isinstance(hash1, str)
    assert len(hash1) == 32  # MD5 hex is 32 chars

    # Same content should produce same hash
    note2 = tmp_path / "test2.note"
    note2.write_bytes(b"test content")
    hash2 = calculate_file_hash(note2)
    assert hash1 == hash2

    # Different content should produce different hash
    note3 = tmp_path / "test3.note"
    note3.write_bytes(b"different content")
    hash3 = calculate_file_hash(note3)
    assert hash1 != hash3


# =============================================================================
# Scan Directory Tests
# =============================================================================


def test_scan_finds_note_files(tmp_path):
    """Test recursive .note file discovery."""
    # Create test structure
    work_dir = tmp_path / "WORK"
    work_dir.mkdir()
    (work_dir / "20260101_test.note").write_bytes(b"test")
    (tmp_path / "other.txt").write_text("not a note")

    results = scan_source_directory(tmp_path)
    assert len(results) == 1
    assert results[0]["file_name"] == "20260101_test.note"


def test_scan_ignores_non_note_files(tmp_path):
    """Test that only .note files are discovered."""
    (tmp_path / "test.txt").write_text("text")
    (tmp_path / "test.pdf").write_bytes(b"pdf")
    (tmp_path / "20260101_valid.note").write_bytes(b"note")

    results = scan_source_directory(tmp_path)
    assert len(results) == 1
    assert results[0]["file_name"] == "20260101_valid.note"


def test_scan_recursive_discovery(tmp_path):
    """Test recursive directory traversal."""
    # Create nested structure
    (tmp_path / "level1").mkdir()
    (tmp_path / "level1" / "level2").mkdir()
    (tmp_path / "20260101_root.note").write_bytes(b"root")
    (tmp_path / "level1" / "20260102_level1.note").write_bytes(b"l1")
    (tmp_path / "level1" / "level2" / "20260103_level2.note").write_bytes(b"l2")

    results = scan_source_directory(tmp_path)
    assert len(results) == 3

    filenames = {r["file_name"] for r in results}
    assert filenames == {
        "20260101_root.note",
        "20260102_level1.note",
        "20260103_level2.note",
    }


def test_scan_cutoff_filters_old_files(tmp_path):
    """Test cutoff date filtering."""
    (tmp_path / "20250101_old.note").write_bytes(b"old")
    (tmp_path / "20260115_new.note").write_bytes(b"new")

    results = scan_source_directory(tmp_path, cutoff_date=date(2026, 1, 1))
    assert len(results) == 1
    assert results[0]["file_name"] == "20260115_new.note"


def test_scan_cutoff_includes_cutoff_date(tmp_path):
    """Test that files matching cutoff date are included."""
    (tmp_path / "20260101_cutoff.note").write_bytes(b"cutoff")
    (tmp_path / "20251231_before.note").write_bytes(b"before")

    results = scan_source_directory(tmp_path, cutoff_date=date(2026, 1, 1))
    assert len(results) == 1
    assert results[0]["file_name"] == "20260101_cutoff.note"


def test_scan_result_structure(tmp_path):
    """Test that scan results have correct structure."""
    note = tmp_path / "20260107_test.note"
    note.write_bytes(b"content")

    results = scan_source_directory(tmp_path)
    assert len(results) == 1

    result = results[0]
    # Check required fields exist
    assert "file_path" in result
    assert "file_name" in result
    assert "file_modified_at" in result
    assert "source_folder" in result
    assert "output_folder" in result
    assert "file_hash" in result
    assert "file_size_bytes" in result

    # Check field types and values
    assert result["file_name"] == "20260107_test.note"
    assert isinstance(result["file_modified_at"], str)  # ISO 8601 string
    assert result["file_size_bytes"] == 7  # "content" is 7 bytes
    assert len(result["file_hash"]) == 32  # MD5 hex


def test_source_folder_categorization_work(tmp_path):
    """Test WORK folder categorization."""
    work_dir = tmp_path / "WORK"
    work_dir.mkdir()
    (work_dir / "20260101_work.note").write_bytes(b"work")

    results = scan_source_directory(tmp_path)
    assert results[0]["source_folder"] == "WORK"
    assert results[0]["output_folder"] == "Journals/Work/"


def test_source_folder_categorization_daily_journal(tmp_path):
    """Test Daily Journal folder categorization."""
    daily_dir = tmp_path / "Daily Journal"
    daily_dir.mkdir()
    (daily_dir / "20260101_daily.note").write_bytes(b"daily")

    results = scan_source_directory(tmp_path)
    assert results[0]["source_folder"] == "Daily Journal"
    assert results[0]["output_folder"] == "Journals/Daily/"


def test_source_folder_categorization_other(tmp_path):
    """Test Other folder categorization."""
    (tmp_path / "20260101_other.note").write_bytes(b"other")

    results = scan_source_directory(tmp_path)
    assert results[0]["source_folder"] == "Other"
    assert results[0]["output_folder"] == "Journals/Other/"


def test_source_folder_nested_work(tmp_path):
    """Test WORK folder detected in nested path."""
    nested = tmp_path / "some" / "nested" / "WORK"
    nested.mkdir(parents=True)
    (nested / "20260101_nested.note").write_bytes(b"nested")

    results = scan_source_directory(tmp_path)
    assert results[0]["source_folder"] == "WORK"
    assert results[0]["output_folder"] == "Journals/Work/"


# =============================================================================
# Scan and Insert Tests (with database)
# =============================================================================


@pytest.fixture
def test_db(tmp_path):
    """Set up test database."""
    db_path = tmp_path / "test.db"
    set_db_path(db_path)
    init_db()
    yield
    # Cleanup handled by tmp_path fixture


def test_scan_and_insert_new_notes(tmp_path, test_db):
    """Test inserting new notes into database."""
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    (notes_dir / "20260101_test.note").write_bytes(b"test")

    new, updated, skipped = scan_and_insert(notes_dir)

    assert new == 1
    assert updated == 0
    assert skipped == 0


def test_scan_and_insert_unchanged_notes(tmp_path, test_db):
    """Test that unchanged notes are skipped."""
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    note_path = notes_dir / "20260101_test.note"
    note_path.write_bytes(b"test")

    # First scan - should insert
    new1, updated1, skipped1 = scan_and_insert(notes_dir)
    assert new1 == 1
    assert skipped1 == 0

    # Second scan - should skip (unchanged)
    new2, updated2, skipped2 = scan_and_insert(notes_dir)
    assert new2 == 0
    assert updated2 == 0
    assert skipped2 == 1


def test_scan_and_insert_updated_notes(tmp_path, test_db):
    """Test that modified notes are detected and updated."""
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    note_path = notes_dir / "20260101_test.note"
    note_path.write_bytes(b"original")

    # First scan
    scan_and_insert(notes_dir)

    # Modify the file
    note_path.write_bytes(b"modified content")

    # Second scan - should detect change
    new, updated, skipped = scan_and_insert(notes_dir)
    assert new == 0
    assert updated == 1
    assert skipped == 0


def test_scan_and_insert_mixed_scenario(tmp_path, test_db):
    """Test mix of new, updated, and skipped notes."""
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()

    # Create initial notes
    (notes_dir / "20260101_existing.note").write_bytes(b"existing")
    (notes_dir / "20260102_toupdate.note").write_bytes(b"original")

    # First scan
    scan_and_insert(notes_dir)

    # Modify one, add one new, leave one unchanged
    (notes_dir / "20260102_toupdate.note").write_bytes(b"updated")
    (notes_dir / "20260103_new.note").write_bytes(b"new")

    # Second scan
    new, updated, skipped = scan_and_insert(notes_dir)
    assert new == 1
    assert updated == 1
    assert skipped == 1


def test_scan_and_insert_with_cutoff(tmp_path, test_db):
    """Test cutoff date filtering in scan_and_insert."""
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    (notes_dir / "20250101_old.note").write_bytes(b"old")
    (notes_dir / "20260101_new.note").write_bytes(b"new")

    new, updated, skipped = scan_and_insert(notes_dir, cutoff_date=date(2026, 1, 1))

    assert new == 1  # Only the new one
    assert updated == 0
    assert skipped == 0


def test_scan_and_insert_respects_source_path_from_config(tmp_path, test_db, monkeypatch):
    """Test that scan_and_insert uses source_path from config when not provided."""
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    (notes_dir / "20260101_test.note").write_bytes(b"test")

    # Mock get_settings to return our test path
    from app.config import Settings

    test_settings = Settings(
        source_path=str(notes_dir),
        output_path=str(tmp_path / "output"),
    )

    monkeypatch.setattr("app.services.scanner.get_settings", lambda: test_settings)

    # Call without source_path parameter - should use config
    new, updated, skipped = scan_and_insert()

    assert new == 1


# =============================================================================
# Integration Test with Real Fixtures
# =============================================================================


def test_scan_real_fixtures(test_db):
    """Test scanning the real test fixtures directory."""
    fixtures_path = Path("tests/fixtures")
    if not fixtures_path.exists():
        pytest.skip("Fixtures directory not found")

    new, updated, skipped = scan_and_insert(fixtures_path)

    # Should find 7 notes (3 Daily Journal, 3 WORK, 1 Other)
    assert new == 7
    assert updated == 0
    assert skipped == 0

    # Verify categorization - use as_posix() to match scanner normalization
    work_note = get_note_by_path((fixtures_path / "WORK" / "20250925_164518.note").as_posix())
    assert work_note is not None
    assert work_note["source_folder"] == "WORK"
    assert work_note["output_folder"] == "Journals/Work/"

    daily_note = get_note_by_path(
        (fixtures_path / "Daily Journal" / "20260107_212138.note").as_posix()
    )
    assert daily_note is not None
    assert daily_note["source_folder"] == "Daily Journal"
    assert daily_note["output_folder"] == "Journals/Daily/"

    other_note = get_note_by_path(
        (fixtures_path / "20251222_Note to Maggie.note").as_posix()
    )
    assert other_note is not None
    assert other_note["source_folder"] == "Other"
    assert other_note["output_folder"] == "Journals/Other/"

    # Re-scan should skip all
    new2, updated2, skipped2 = scan_and_insert(fixtures_path)
    assert new2 == 0
    assert updated2 == 0
    assert skipped2 == 7
