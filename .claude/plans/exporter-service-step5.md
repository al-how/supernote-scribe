# Implementation Plan: Step 5 - Exporter Service

## Overview

Implement the Exporter service that converts `.note` files to PNG images using `supernotelib`. This is a critical service that sits between Scanner (Step 4) and OCR (Step 6) in the pipeline.

**Data Flow:** Scan → **Export to PNG** → Vision OCR → Review → Save

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| [app/services/exporter.py](app/services/exporter.py) | Create | Main exporter service |
| [tests/test_exporter.py](tests/test_exporter.py) | Create | Unit and integration tests |
| [app/services/__init__.py](app/services/__init__.py) | Modify | Export new functions |

## Implementation Details

### 1. Core Functions

```python
# app/services/exporter.py

def export_note_to_png(
    note_path: Path,
    output_dir: Path | None = None,
) -> list[Path]:
    """
    Export all pages of a .note file to PNG images.

    Args:
        note_path: Path to the .note file
        output_dir: Directory for PNGs (defaults to config png_cache_path)

    Returns:
        List of paths to exported PNG files, ordered by page number

    Raises:
        FileNotFoundError: If note_path doesn't exist
        ValueError: If file is not a valid .note file
    """

def export_note_by_id(note_id: int) -> list[Path]:
    """
    Export note from database by ID, updating page_count.

    Handles:
    - Look up note path from database
    - Create PNG cache subdirectory
    - Export all pages
    - Update note's page_count in database
    - Return list of PNG paths

    Raises:
        ValueError: If note_id not found
    """

def get_page_count(note_path: Path) -> int:
    """
    Get number of pages in a .note file without exporting.

    Useful for progress tracking before batch export.
    """
```

### 2. supernotelib API Usage

Based on research, the actual supernotelib API:

```python
from supernotelib import parser
from supernotelib.converter import ImageConverter
from supernotelib.tools import VisibilityOverlay

def export_note_to_png(note_path: Path, output_dir: Path) -> list[Path]:
    # Load notebook
    notebook = parser.load_notebook(str(note_path))

    # Get page count
    total_pages = notebook.get_total_pages()

    # Create image converter
    image_converter = ImageConverter(notebook)

    png_paths = []
    for page_num in range(total_pages):
        # Convert page to PIL Image
        pil_image = image_converter.convert(
            page_num,
            visibility_overlay=VisibilityOverlay.DEFAULT
        )

        # Save to PNG
        png_path = output_dir / f"{note_path.stem}_{page_num}.png"
        pil_image.save(str(png_path), format='PNG')
        png_paths.append(png_path)

    return png_paths
```

### 3. PNG Cache Organization

```
data/png_cache/
├── {note_id}/                    # Subdirectory per note
│   ├── {note_stem}_0.png
│   ├── {note_stem}_1.png
│   └── ...
```

Using note_id as subdirectory:
- Avoids filename collisions between notes with same name
- Easy cleanup when note is deleted
- Clear association with database record

### 4. Error Handling

| Error Case | Handling |
|------------|----------|
| File not found | Raise `FileNotFoundError` |
| Invalid .note file | Catch supernotelib exception, raise `ValueError` with message |
| Export failure (single page) | Log error, continue with other pages, return partial results |
| Output dir not writable | Raise `PermissionError` |

### 5. Database Integration

```python
from app.database import (
    get_note_by_id,
    update_note_page_count,
    mark_note_error,
)
from app.config import get_settings
```

After export:
- Call `update_note_page_count(note_id, len(png_paths))`
- Store PNG paths for later use by OCR service

## Test Plan (TDD Approach)

### Test Cases (tests/test_exporter.py)

```python
# 1. Basic Export Tests
def test_export_single_page_note(tmp_path):
    """Export generates 1 PNG for single-page note."""

def test_export_multi_page_note(tmp_path):
    """Export generates N PNGs for multi-page note."""

def test_png_filenames_follow_convention(tmp_path):
    """PNGs named {stem}_{page}.png (0-indexed)."""

# 2. Error Handling Tests
def test_export_nonexistent_file_raises():
    """FileNotFoundError for missing file."""

def test_export_invalid_file_raises(tmp_path):
    """ValueError for non-.note file."""

# 3. Output Directory Tests
def test_export_creates_output_dir(tmp_path):
    """Output directory created if missing."""

def test_export_uses_config_path_when_none():
    """Uses png_cache_path from config when output_dir=None."""

# 4. Database Integration Tests
def test_export_note_by_id_updates_page_count(test_db, tmp_path):
    """page_count updated in database after export."""

def test_export_note_by_id_not_found_raises(test_db):
    """ValueError for invalid note_id."""

# 5. Integration Tests with Real Fixtures
def test_export_real_fixture_note():
    """Export real .note file from tests/fixtures/."""
```

### Test Fixtures Needed

Already available in `tests/fixtures/`:
- 7 real `.note` files for integration testing
- Can determine single vs multi-page after first export test

### Fixture Setup (conftest.py additions)

```python
@pytest.fixture
def png_output_dir(tmp_path):
    """Temporary directory for PNG output."""
    output_dir = tmp_path / "png_cache"
    output_dir.mkdir()
    return output_dir

@pytest.fixture
def sample_note_path():
    """Path to a real single-page .note fixture."""
    return Path("tests/fixtures/20251222_Note to Maggie.note")
```

## Implementation Steps

### Phase 1: Write Tests First (TDD)
1. Create `tests/test_exporter.py` with all test cases
2. Add fixtures to `tests/conftest.py` if needed
3. Run tests (all should fail initially)

### Phase 2: Implement Core Functions
1. Create `app/services/exporter.py`
2. Implement `get_page_count()` - simplest function
3. Implement `export_note_to_png()` - core export logic
4. Run tests, fix until passing

### Phase 3: Add Database Integration
1. Implement `export_note_by_id()`
2. Add database tests
3. Run full test suite

### Phase 4: Update Module Exports
1. Add exports to `app/services/__init__.py`
2. Verify imports work

## Code Patterns (following scanner.py)

```python
"""Exporter service for converting .note files to PNG."""
from pathlib import Path

from app.config import get_settings
from app.database import (
    get_note_by_id,
    update_note_page_count,
    mark_note_error,
)


def helper_function(param: str) -> str | None:
    """
    Short description.

    Args:
        param: Description

    Returns:
        Description
    """
    pass


def main_function(
    required_param: Path,
    optional_param: Path | None = None,
) -> list[Path]:
    """
    Main description.

    Detailed explanation.

    Args:
        required_param: Description
        optional_param: Override config value (defaults to settings)

    Returns:
        Description of return value

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is invalid
    """
    if optional_param is None:
        settings = get_settings()
        optional_param = settings.png_cache_path

    # Implementation
    pass
```

## Verification

### Manual Testing
After implementation, test with real file:
```python
from app.services.exporter import export_note_to_png
from pathlib import Path

pngs = export_note_to_png(Path("tests/fixtures/20251222_Note to Maggie.note"))
print(f"Exported {len(pngs)} pages")
# Open PNG files to visually verify
```

### Automated Testing
```bash
# Run all exporter tests
pytest tests/test_exporter.py -v

# Run with coverage
pytest tests/test_exporter.py --cov=app.services.exporter

# Run full test suite
pytest tests/ -v
```

## Dependencies

Already in `requirements.txt`:
- `supernotelib>=0.5.0`
- `Pillow>=10.0.0` (for PIL Image handling)

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| supernotelib API differs from docs | Test with real .note files early, adapt code |
| Multi-page note detection | Use `get_total_pages()` API |
| Large notes cause memory issues | Process one page at a time, don't hold all in memory |
| Corrupted .note files | Wrap in try/except, mark note as error |

## Success Criteria

1. All tests pass (`pytest tests/test_exporter.py`)
2. Can export all 7 test fixture files
3. PNG files are valid images (viewable)
4. Database page_count updated correctly
5. Follows existing code patterns (scanner.py style)
