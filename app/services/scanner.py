"""Scanner service for discovering .note files."""
import hashlib
from datetime import datetime, date
from pathlib import Path
from typing import Generator

from app.config import get_settings, Settings
from app.database import (
    determine_output_folder,
    determine_source_folder,
    get_note_by_path,
    upsert_note,
)


def _get_effective_settings() -> Settings:
    """Get settings with database overrides applied."""
    from app.settings_manager import SettingsManager
    return Settings(**SettingsManager().get_all())


def extract_date_from_filename(filename: str) -> date | None:
    """
    Extract date from Supernote filename.

    Expected format: YYYYMMDD_* (e.g., "20260107_212138.note")
    Returns None if filename doesn't have date prefix.

    Args:
        filename: The filename to parse

    Returns:
        Parsed date or None if no valid date prefix found
    """
    if len(filename) < 8:
        return None

    date_str = filename[:8]

    # Check if first 8 chars are all digits
    if not date_str.isdigit():
        return None

    try:
        return datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        return None


def get_note_date(file_path: Path) -> date:
    """
    Get date for a note file.

    Tries filename first, falls back to file modification time.

    Args:
        file_path: Path to the note file

    Returns:
        Date from filename or file modification time
    """
    parsed = extract_date_from_filename(file_path.name)
    if parsed:
        return parsed

    # Fallback to file modification time
    mtime = file_path.stat().st_mtime
    return datetime.fromtimestamp(mtime).date()


def calculate_file_hash(file_path: Path) -> str:
    """
    Calculate MD5 hash of file contents for change detection.

    Reads file in chunks to handle large files efficiently.

    Args:
        file_path: Path to the file

    Returns:
        MD5 hex digest (32 characters)
    """
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as f:
        # Read in 64kb chunks
        for chunk in iter(lambda: f.read(65536), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def scan_source_directory(
    source_path: Path | None = None,
    cutoff_date: date | None = None,
) -> list[dict]:
    """
    Discover all .note files in source directory.

    Args:
        source_path: Override source path (defaults to config)
        cutoff_date: Only include files with date >= cutoff

    Returns:
        List of discovered note metadata dicts with keys:
        - file_path: Full path as string (normalized with forward slashes)
        - file_name: Just the filename
        - file_modified_at: ISO 8601 timestamp string
        - source_folder: "WORK", "Daily Journal", or "Other"
        - output_folder: "Journals/Work/", "Journals/Daily/", or "Journals/Other/"
        - file_hash: MD5 hex digest
        - file_size_bytes: File size in bytes
    """
    if source_path is None:
        settings = _get_effective_settings()
        source_path = Path(settings.source_path)

    results = []

    # Recursively find all .note files
    for note_path in source_path.rglob("*.note"):
        # Get note date (from filename or mtime)
        note_date = get_note_date(note_path)

        # Apply cutoff filter
        if cutoff_date is not None and note_date < cutoff_date:
            continue

        # Get file metadata
        stat = note_path.stat()
        file_modified_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
        file_size_bytes = stat.st_size
        file_hash = calculate_file_hash(note_path)

        # Normalize path for database (forward slashes, cross-platform)
        normalized_path = note_path.as_posix()

        # Determine source and output folders
        source_folder = determine_source_folder(normalized_path)
        output_folder = determine_output_folder(source_folder)

        results.append({
            "file_path": normalized_path,
            "file_name": note_path.name,
            "file_modified_at": file_modified_at,
            "source_folder": source_folder,
            "output_folder": output_folder,
            "file_hash": file_hash,
            "file_size_bytes": file_size_bytes,
        })

    return results


def scan_and_insert(
    source_path: Path | None = None,
    cutoff_date: date | None = None,
) -> tuple[int, int, int]:
    """
    Scan for .note files and insert/update database records.

    This function:
    1. Scans the source directory for .note files
    2. For each file, checks if it exists in the database
    3. Inserts new notes or updates changed notes
    4. Tracks counts for reporting

    Args:
        source_path: Override source path (defaults to config)
        cutoff_date: Only include files with date >= cutoff

    Returns:
        Tuple of (new_count, updated_count, skipped_count)
        - new_count: Number of newly inserted notes
        - updated_count: Number of notes that were modified and updated
        - skipped_count: Number of notes that were unchanged
    """
    new_count = 0
    updated_count = 0
    skipped_count = 0

    # Scan for notes
    discovered_notes = scan_source_directory(source_path, cutoff_date)

    for note_info in discovered_notes:
        file_path = note_info["file_path"]
        file_modified_at = note_info["file_modified_at"]
        file_hash = note_info["file_hash"]

        # Check if note exists in database
        existing = get_note_by_path(file_path)

        # Upsert the note
        upsert_note(
            file_path=file_path,
            file_name=note_info["file_name"],
            file_modified_at=file_modified_at,
            source_folder=note_info["source_folder"],
            output_folder=note_info["output_folder"],
            file_hash=file_hash,
            file_size_bytes=note_info["file_size_bytes"],
        )

        # Determine what happened and track counts
        if existing is None:
            # New note inserted
            new_count += 1
        elif (
            existing["file_modified_at"] != file_modified_at
            or (file_hash and existing["file_hash"] != file_hash)
        ):
            # Note was modified (different mtime or hash)
            updated_count += 1
        else:
            # Note unchanged
            skipped_count += 1

    return new_count, updated_count, skipped_count
