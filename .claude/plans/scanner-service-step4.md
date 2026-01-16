# Plan: Scanner Service (Step 4)

## Overview

Create `app/services/scanner.py` - a service to discover `.note` files, parse dates from filenames, categorize by source folder, and insert/update records in the database.

## Filename Pattern Discovery

From sample files provided:
```
tests/fixtures/Daily Journal/20260107_212138.note   # YYYYMMDD_HHMMSS
tests/fixtures/Daily Journal/20260104_211808.note
tests/fixtures/20251222_Note to Maggie.note         # YYYYMMDD_Description
tests/fixtures/WORK/20250925_164518.note
tests/fixtures/WORK/20260106_194253.note
tests/fixtures/WORK/Florida.note                    # Description only (no date)
```

**Date formats (in priority order):**
1. `YYYYMMDD_*.note` - Date prefix (first 8 chars are digits)
2. `Description.note` - No date prefix → **fallback to file modification time**

The scanner must handle files without date prefixes gracefully.

## Cross-Platform Considerations

| Aspect | Windows (Dev) | Linux (Unraid Prod) |
|--------|---------------|---------------------|
| Path separator | `\` | `/` |
| Case sensitivity | Case-insensitive | Case-sensitive |
| Glob behavior | Works with pathlib | Works with pathlib |

**Solution:** Use `pathlib.Path` throughout. Normalize paths with `.as_posix()` for database storage and comparison. The existing `determine_source_folder()` in database.py already normalizes with `replace("\\", "/")`.

## Implementation

### File: `app/services/scanner.py`

```python
"""Scanner service for discovering .note files."""
from pathlib import Path
from datetime import datetime, date
from typing import Generator
import hashlib

from app.database import (
    upsert_note,
    get_note_by_path,
    determine_source_folder,
    determine_output_folder,
)
from app.config import get_settings

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
        List of discovered note metadata dicts
    """
    ...

def extract_date_from_filename(filename: str) -> date | None:
    """
    Extract date from Supernote filename.

    Expected format: YYYYMMDD_* (e.g., "20260107_212138.note")
    Returns None if filename doesn't have date prefix.
    """
    ...

def get_note_date(file_path: Path) -> date:
    """
    Get date for a note file.

    Tries filename first, falls back to file modification time.
    """
    ...

def calculate_file_hash(file_path: Path) -> str:
    """Calculate MD5 hash of file contents for change detection."""
    ...

def scan_and_insert(
    source_path: Path | None = None,
    cutoff_date: date | None = None,
) -> tuple[int, int, int]:
    """
    Scan for .note files and insert/update database records.

    Returns:
        Tuple of (new_count, updated_count, skipped_count)
    """
    ...
```

### Key Functions

#### 1. `extract_date_from_filename(filename: str) -> date | None`
```python
def extract_date_from_filename(filename: str) -> date | None:
    """
    Extract date from YYYYMMDD prefix.

    Returns None if filename doesn't start with 8 digits (caller should use mtime).
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
```

#### 2. `get_note_date(file_path: Path) -> date`
```python
def get_note_date(file_path: Path) -> date:
    """
    Get date for a note file.

    Tries filename first, falls back to file modification time.
    """
    parsed = extract_date_from_filename(file_path.name)
    if parsed:
        return parsed

    # Fallback to file modification time
    mtime = file_path.stat().st_mtime
    return datetime.fromtimestamp(mtime).date()
```

#### 3. `scan_source_directory(...)`
- Use `Path.rglob("*.note")` for recursive discovery
- For each file:
  - Extract date from filename (fallback to mtime if parsing fails)
  - Apply cutoff filter if provided
  - Determine source folder from path
  - Build metadata dict
- Return list of metadata dicts (not yet inserted)

#### 4. `calculate_file_hash(file_path: Path) -> str`
- Read file in chunks to handle large files
- Return MD5 hex digest
- Used for change detection in `upsert_note()`

#### 5. `scan_and_insert(...)`
- Call `scan_source_directory()` to discover files
- For each file, call `upsert_note()` with full metadata
- Track counts: new inserts, updates (file changed), skipped (unchanged)
- Return counts tuple for UI feedback

### Integration Points

**Uses from existing code:**
- `app.config.get_settings()` - Get `source_path`
- `app.database.upsert_note()` - Insert/update note records
- `app.database.get_note_by_path()` - Check if note exists (for tracking counts)
- `app.database.determine_source_folder()` - Categorize by path
- `app.database.determine_output_folder()` - Map to output folder

**Used by (future):**
- `app/pages/1_Scan.py` - UI trigger for scanning
- `app/__main__.py` - CLI `--process` flag

### Database API Details

#### `upsert_note()` Function Signature (from database.py:306)

```python
def upsert_note(
    file_path: str,           # Required - full path (unique key for deduplication)
    file_name: str,           # Required - just the filename
    file_modified_at: str,    # Required - ISO 8601 string from file mtime
    source_folder: str,       # Required - "WORK", "Daily Journal", or "Other"
    output_folder: str,       # Required - "Journals/Work/", "Journals/Daily/", "Journals/Other/"
    file_hash: str | None = None,       # Optional - MD5 for change detection
    file_size_bytes: int | None = None, # Optional
    page_count: int | None = None,      # Optional - set later by exporter
) -> int:  # Returns note ID
```

#### Change Detection Logic

`upsert_note()` handles three scenarios internally:

| Scenario | Condition | Action |
|----------|-----------|--------|
| New insert | Note doesn't exist | INSERT new row |
| Update | Note exists AND (mtime differs OR hash differs) | UPDATE row, reset `status='pending'` |
| Skip | Note exists AND unchanged | Return existing ID (no update) |

**Important:** `upsert_note()` only returns the note ID - it doesn't indicate which scenario occurred.

#### Tracking New/Updated/Skipped Counts

The scanner must query before upserting to track counts:

```python
from app.database import get_note_by_path, upsert_note

def scan_and_insert(...) -> tuple[int, int, int]:
    new_count = updated_count = skipped_count = 0

    for file_info in scan_source_directory(...):
        file_path = file_info["file_path"]
        file_modified_at = file_info["file_modified_at"]
        file_hash = file_info["file_hash"]

        # Check existing state BEFORE upsert
        existing = get_note_by_path(file_path)

        # Perform upsert
        upsert_note(
            file_path=file_path,
            file_name=file_info["file_name"],
            file_modified_at=file_modified_at,
            source_folder=file_info["source_folder"],
            output_folder=file_info["output_folder"],
            file_hash=file_hash,
            file_size_bytes=file_info["file_size_bytes"],
        )

        # Track what happened
        if existing is None:
            new_count += 1
        elif (existing["file_modified_at"] != file_modified_at or
              (file_hash and existing["file_hash"] != file_hash)):
            updated_count += 1
        else:
            skipped_count += 1

    return new_count, updated_count, skipped_count
```

## Test Plan

Create `tests/test_scanner.py`:

```python
def test_extract_date_standard_format():
    """Test YYYYMMDD_HHMMSS.note format."""
    assert extract_date_from_filename("20260107_212138.note") == date(2026, 1, 7)

def test_extract_date_with_description():
    """Test YYYYMMDD_Description.note format."""
    assert extract_date_from_filename("20251222_Note to Maggie.note") == date(2025, 12, 22)

def test_extract_date_no_date_prefix_returns_none():
    """Test filename without date prefix returns None (use mtime fallback)."""
    assert extract_date_from_filename("Florida.note") is None
    assert extract_date_from_filename("Meeting Notes.note") is None
    assert extract_date_from_filename("abc.note") is None

def test_get_note_date_uses_mtime_fallback(tmp_path):
    """Test that files without date prefix use file mtime."""
    note = tmp_path / "Florida.note"
    note.write_bytes(b"test")

    result = get_note_date(note)
    assert result == date.today()  # mtime is now

def test_scan_finds_note_files(tmp_path):
    """Test recursive .note file discovery."""
    # Create test structure
    (tmp_path / "WORK").mkdir()
    (tmp_path / "WORK" / "20260101_test.note").write_bytes(b"test")
    (tmp_path / "other.txt").write_text("not a note")

    results = scan_source_directory(tmp_path)
    assert len(results) == 1
    assert results[0]["file_name"] == "20260101_test.note"

def test_scan_cutoff_filters_old_files(tmp_path):
    """Test cutoff date filtering."""
    (tmp_path / "20250101_old.note").write_bytes(b"old")
    (tmp_path / "20260115_new.note").write_bytes(b"new")

    results = scan_source_directory(tmp_path, cutoff_date=date(2026, 1, 1))
    assert len(results) == 1
    assert results[0]["file_name"] == "20260115_new.note"

def test_source_folder_categorization(tmp_path):
    """Test WORK/Daily Journal/Other categorization."""
    work_dir = tmp_path / "WORK"
    work_dir.mkdir()
    (work_dir / "20260101_work.note").write_bytes(b"work")

    results = scan_source_directory(tmp_path)
    assert results[0]["source_folder"] == "WORK"
    assert results[0]["output_folder"] == "Journals/Work/"
```

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `app/services/scanner.py` | CREATE | Main scanner service |
| `tests/test_scanner.py` | CREATE | Unit tests |
| `app/services/__init__.py` | MODIFY | Export scanner functions |

## Verification

1. **Unit tests pass:** `pytest tests/test_scanner.py -v`
2. **Manual test with fixtures:**
   ```python
   from app.services.scanner import scan_and_insert
   from pathlib import Path

   new, updated, skipped = scan_and_insert(
       source_path=Path("tests/fixtures"),
       cutoff_date=None
   )
   print(f"New: {new}, Updated: {updated}, Skipped: {skipped}")
   ```
3. **Check database:** Verify 7 notes inserted with correct source_folder values (3 Daily Journal, 3 WORK, 1 Other)
4. **Re-run scan:** Should show 0 new, 0 updated, 7 skipped (deduplication works)

## Decisions Made

- **Hash algorithm:** MD5 (fast, sufficient for change detection)
