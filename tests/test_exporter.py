"""Tests for exporter service."""
from pathlib import Path

import pytest

from app.database import (
    get_note_by_id,
    insert_note,
)
from app.services.exporter import (
    export_note_by_id,
    export_note_to_png,
    get_page_count,
)


# Fixtures are defined in conftest.py: test_db, png_output_dir, sample_note_path, work_note_path


# =============================================================================
# Basic Export Tests
# =============================================================================


def test_export_note_generates_pngs(sample_note_path, png_output_dir):
    """Export generates PNG files for note."""
    if not sample_note_path.exists():
        pytest.skip("Fixture file not found")

    pngs = export_note_to_png(sample_note_path, png_output_dir)

    assert len(pngs) >= 1
    for png_path in pngs:
        assert png_path.exists()
        assert png_path.suffix == ".png"


def test_export_png_filenames_follow_convention(sample_note_path, png_output_dir):
    """PNGs named {stem}_{page}.png (0-indexed)."""
    if not sample_note_path.exists():
        pytest.skip("Fixture file not found")

    pngs = export_note_to_png(sample_note_path, png_output_dir)

    # Check naming convention: stem_0.png, stem_1.png, etc.
    stem = sample_note_path.stem
    for i, png_path in enumerate(pngs):
        expected_name = f"{stem}_{i}.png"
        assert png_path.name == expected_name


def test_export_returns_paths_in_order(sample_note_path, png_output_dir):
    """Exported PNG paths are in page order (0, 1, 2...)."""
    if not sample_note_path.exists():
        pytest.skip("Fixture file not found")

    pngs = export_note_to_png(sample_note_path, png_output_dir)

    for i, png_path in enumerate(pngs):
        assert f"_{i}.png" in png_path.name


# =============================================================================
# Error Handling Tests
# =============================================================================


def test_export_nonexistent_file_raises():
    """FileNotFoundError for missing file."""
    with pytest.raises(FileNotFoundError):
        export_note_to_png(Path("/nonexistent/path/note.note"))


def test_export_invalid_file_raises(tmp_path):
    """ValueError for non-.note file (invalid format)."""
    # Create a fake .note file with invalid content
    fake_note = tmp_path / "fake.note"
    fake_note.write_bytes(b"not a valid supernote file")

    with pytest.raises(ValueError):
        export_note_to_png(fake_note, tmp_path)


# =============================================================================
# Output Directory Tests
# =============================================================================


def test_export_creates_output_dir(sample_note_path, tmp_path):
    """Output directory created if missing."""
    if not sample_note_path.exists():
        pytest.skip("Fixture file not found")

    output_dir = tmp_path / "new_output_dir"
    assert not output_dir.exists()

    pngs = export_note_to_png(sample_note_path, output_dir)

    assert output_dir.exists()
    assert len(pngs) >= 1


def test_export_uses_config_path_when_none(sample_note_path, tmp_path, monkeypatch):
    """Uses png_cache_path from config when output_dir=None."""
    if not sample_note_path.exists():
        pytest.skip("Fixture file not found")

    # Create a mock settings object
    from app.config import Settings

    png_cache = tmp_path / "config_png_cache"
    test_settings = Settings(
        source_path=str(tmp_path / "source"),
        output_path=str(tmp_path / "output"),
        png_cache_path=str(png_cache),
    )

    monkeypatch.setattr("app.services.exporter._get_effective_settings", lambda: test_settings)

    # Call without output_dir - should use config path
    pngs = export_note_to_png(sample_note_path)

    assert png_cache.exists()
    assert len(pngs) >= 1
    for png_path in pngs:
        assert str(png_cache) in str(png_path)


# =============================================================================
# Page Count Tests
# =============================================================================


def test_get_page_count_returns_positive(sample_note_path):
    """get_page_count returns positive integer."""
    if not sample_note_path.exists():
        pytest.skip("Fixture file not found")

    count = get_page_count(sample_note_path)

    assert isinstance(count, int)
    assert count >= 1


def test_get_page_count_nonexistent_raises():
    """FileNotFoundError for missing file."""
    with pytest.raises(FileNotFoundError):
        get_page_count(Path("/nonexistent/path/note.note"))


def test_get_page_count_invalid_file_raises(tmp_path):
    """ValueError for invalid .note file."""
    fake_note = tmp_path / "fake.note"
    fake_note.write_bytes(b"not valid")

    with pytest.raises(ValueError):
        get_page_count(fake_note)


# =============================================================================
# Database Integration Tests
# =============================================================================


def test_export_note_by_id_updates_page_count(test_db, tmp_path, monkeypatch):
    """page_count updated in database after export."""
    sample_note_path = Path("tests/fixtures/20251222_Note to Maggie.note")
    if not sample_note_path.exists():
        pytest.skip("Fixture file not found")

    # Set up mock config for png_cache_path
    from app.config import Settings

    png_cache = tmp_path / "png_cache"
    test_settings = Settings(
        source_path=str(tmp_path / "source"),
        output_path=str(tmp_path / "output"),
        png_cache_path=str(png_cache),
    )
    monkeypatch.setattr("app.services.exporter._get_effective_settings", lambda: test_settings)

    # Insert a note into the database
    note_id = insert_note(
        file_path=sample_note_path.as_posix(),
        file_name=sample_note_path.name,
        file_modified_at="2025-12-22T00:00:00",
        source_folder="Other",
        output_folder="Journals/Other/",
        page_count=0,
    )

    # Verify initial page_count is 0
    note = get_note_by_id(note_id)
    assert note["page_count"] == 0

    # Export by ID
    pngs = export_note_by_id(note_id)

    # Verify page_count was updated
    note = get_note_by_id(note_id)
    assert note["page_count"] == len(pngs)
    assert note["page_count"] >= 1


def test_export_note_by_id_creates_subdirectory(test_db, tmp_path, monkeypatch):
    """PNG cache uses note_id subdirectory."""
    # Use a different fixture file to avoid collision with test_export_note_by_id_updates_page_count
    note_file = Path("tests/fixtures/WORK/20250925_164518.note")
    if not note_file.exists():
        pytest.skip("Fixture file not found")

    from app.config import Settings

    png_cache = tmp_path / "png_cache"
    test_settings = Settings(
        source_path=str(tmp_path / "source"),
        output_path=str(tmp_path / "output"),
        png_cache_path=str(png_cache),
    )
    monkeypatch.setattr("app.services.exporter._get_effective_settings", lambda: test_settings)

    note_id = insert_note(
        file_path=note_file.as_posix(),
        file_name=note_file.name,
        file_modified_at="2025-09-25T00:00:00",
        source_folder="WORK",
        output_folder="Journals/Work/",
    )

    pngs = export_note_by_id(note_id)

    # Check that PNGs are in a subdirectory named by note_id
    expected_subdir = png_cache / str(note_id)
    assert expected_subdir.exists()
    for png_path in pngs:
        assert str(note_id) in str(png_path.parent)


def test_export_note_by_id_not_found_raises(test_db):
    """ValueError for invalid note_id."""
    with pytest.raises(ValueError, match="not found"):
        export_note_by_id(99999)


# =============================================================================
# Integration Tests with Multiple Real Fixtures
# =============================================================================


def test_export_all_fixtures(png_output_dir):
    """Export all 7 test fixture files."""
    fixtures_dir = Path("tests/fixtures")
    if not fixtures_dir.exists():
        pytest.skip("Fixtures directory not found")

    note_files = list(fixtures_dir.rglob("*.note"))
    assert len(note_files) == 12, f"Expected 12 fixtures, found {len(note_files)}"

    for note_path in note_files:
        # Create subdirectory for each note to avoid collisions
        subdir = png_output_dir / note_path.stem
        subdir.mkdir(exist_ok=True)

        pngs = export_note_to_png(note_path, subdir)

        assert len(pngs) >= 1, f"No PNGs exported for {note_path.name}"
        for png_path in pngs:
            assert png_path.exists(), f"PNG not created: {png_path}"


def test_export_work_note(work_note_path, png_output_dir):
    """Export a WORK note specifically."""
    if not work_note_path.exists():
        pytest.skip("Work fixture not found")

    pngs = export_note_to_png(work_note_path, png_output_dir)

    assert len(pngs) >= 1
    # Verify PNG is valid by checking file size > 0
    for png_path in pngs:
        assert png_path.stat().st_size > 0
