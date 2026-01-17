# Markdown Service Implementation Plan (Step 8)

## Overview

The markdown service is responsible for converting OCR-extracted text into properly formatted Obsidian-compatible markdown files with YAML frontmatter. It will be called after notes are approved (either auto-approved or manually approved via the Review UI).

## Responsibilities

1. **Frontmatter Builder**: Generate YAML frontmatter with metadata
2. **Line Processing**: Intelligent line break handling (port from n8n logic)
3. **Content Assembly**: Combine frontmatter + processed text
4. **File Writer**: Save to correct output path

---

## Detailed Design

### 1. Frontmatter Structure

Based on user requirements, the frontmatter will include:

```yaml
---
created: 2026-01-15          # Date from .note file (extracted from filename or mtime)
processed: 2026-01-16        # Current date when markdown was generated
tags: []                     # Empty array for user to populate later
source_file: /path/to.note   # Original .note file path
---
```

**Fields:**
- `created`: Date the .note was created (from `file_modified_at` in database, or parsed from filename)
- `processed`: Current date/time when markdown file is generated
- `tags`: Empty array placeholder for Obsidian tagging
- `source_file`: Original .note path for traceability

### 2. Line Processing Rules

Port the following logic from plan.md:

| Rule | Description | Example |
|------|-------------|---------|
| **Join incomplete lines** | Lines NOT ending with `.!?:;` should be joined with the next line | `"Hello\nworld" → "Hello world"` |
| **Preserve paragraphs** | Empty lines (paragraph breaks) are preserved | `"Line1\n\nLine2"` stays as-is |
| **Preserve list items** | Lines starting with `-`, `*`, `•`, or `1.` etc. are kept separate | `"- Item one\n- Item two"` preserved |
| **Preserve headers** | Short capitalized lines (likely headers) kept separate | `"INTRODUCTION\n"` preserved |

**Implementation approach:**
```python
def process_line_breaks(text: str) -> str:
    """
    Process OCR text to fix line breaks while preserving structure.

    Rules:
    1. Join lines not ending with sentence-ending punctuation
    2. Preserve empty lines (paragraphs)
    3. Preserve list items (-, *, •, numbered)
    4. Preserve short capitalized lines (headers)
    """
```

### 3. Module Interface

```python
# app/services/markdown.py

def build_frontmatter(
    note: dict,
    processed_at: datetime | None = None,
) -> str:
    """Build YAML frontmatter from note metadata."""

def process_line_breaks(text: str) -> str:
    """Process OCR text to intelligently handle line breaks."""

def build_markdown(
    note: dict,
    extracted_text: str,
    processed_at: datetime | None = None,
) -> str:
    """Build complete markdown file content (frontmatter + processed text)."""

def save_markdown(
    note_id: int,
    output_path: Path | None = None,
) -> Path:
    """
    Build and save markdown for a note.

    Gets aggregated text from database, builds markdown, writes to file.
    Returns the output path.
    """

def save_full_text_edit(note_id: int, edited_text: str) -> None:
    """
    Save a full-text edit, handling multi-page cleanup.

    Stores text in page 0, deletes pages 1..N to prevent duplication.
    Call this BEFORE approve_and_save_note for full-text edits.
    """

def approve_and_save_note(note_id: int) -> Path:
    """
    Approve a note and save markdown file.

    IMPORTANT: Edits must be saved to database BEFORE calling this:
    - Per-page: Use update_extraction_text() for each page
    - Full-text: Use save_full_text_edit() first
    """

def approve_with_full_text_edit(note_id: int, edited_text: str) -> Path:
    """
    Convenience wrapper: save full-text edit + approve in one call.

    Use for single-page notes or simplified UIs.
    """
```

### 4. Integration Points

#### Current Flow (processor.py)
```
process_single_note()
├── export_note_by_id() → PNGs
├── extract_text_from_image() × N pages → extractions table
├── get_aggregated_text() → combined text
└── mark_note_auto_approved(output_path)  ← Currently just marks, doesn't write file
```

#### Updated Flow with Markdown Service
```
process_single_note()
├── export_note_by_id() → PNGs
├── extract_text_from_image() × N pages → extractions table
├── get_aggregated_text() → combined text
└── IF auto_approve threshold met:
    ├── save_markdown(note_id)         ← NEW: actually write the file
    └── mark_note_auto_approved(output_path)
```

#### Review UI Flow (Per-Page Editing - Recommended)
```
User navigates pages, editing text for each
├── On each page save: update_extraction_text(ext_id, edited_text)
│
User clicks Approve
├── approve_and_save_note(note_id)
│   ├── get_aggregated_text() → combines per-page edited_text
│   ├── process_line_breaks(text)
│   ├── build_markdown(note, processed_text)
│   ├── write file to output_path
│   └── mark_note_approved(note_id, output_path)
└── Show success message
```

#### Review UI Flow (Full-Text Editing - Alternative for single-page/simple UI)
```
User edits all text in single text area
│
User clicks Approve
├── approve_with_full_text_edit(note_id, edited_text)
│   ├── save_full_text_edit() → stores in page 0, deletes pages 1..N
│   ├── approve_and_save_note()
│   │   ├── get_aggregated_text() → returns only page 0
│   │   ├── process_line_breaks(text)
│   │   ├── build_markdown(note, processed_text)
│   │   └── write file + mark_note_approved()
└── Show success message
```

---

## Implementation Steps

### Step 8.1: Line Processing Function

**File:** `app/services/markdown.py`

```python
import re
from typing import List

# Punctuation that ends a complete thought
SENTENCE_ENDINGS = {'.', '!', '?', ':', ';'}

# Patterns for list items
LIST_PATTERN = re.compile(r'^[\s]*[-*•][\s]|^[\s]*\d+[.)][\s]')

# Pattern for short capitalized lines (headers)
HEADER_PATTERN = re.compile(r'^[A-Z][A-Z\s]{2,}$')

def _is_list_item(line: str) -> bool:
    """Check if line starts with list marker."""
    return bool(LIST_PATTERN.match(line))

def _is_header(line: str) -> bool:
    """Check if line is a short capitalized header."""
    stripped = line.strip()
    return len(stripped) <= 50 and bool(HEADER_PATTERN.match(stripped))

def _ends_sentence(line: str) -> bool:
    """Check if line ends with sentence-ending punctuation."""
    stripped = line.rstrip()
    return len(stripped) > 0 and stripped[-1] in SENTENCE_ENDINGS

def process_line_breaks(text: str) -> str:
    """Process OCR text to intelligently handle line breaks."""
```

**Test cases to implement:**
- Normal lines get joined: `"Hello\nworld"` → `"Hello world"`
- Sentence-ending preserved: `"Hello.\nWorld"` → `"Hello.\nWorld"`
- List items preserved: `"- Item 1\n- Item 2"` → preserved
- Empty lines (paragraphs) preserved: `"Para1\n\nPara2"` → preserved
- Headers preserved: `"INTRODUCTION\nThis is"` → preserved
- Numbered lists: `"1. First\n2. Second"` → preserved

### Step 8.2: Frontmatter Builder

```python
from datetime import datetime
from pathlib import Path

def build_frontmatter(
    note: dict,
    processed_at: datetime | None = None,
) -> str:
    """
    Build YAML frontmatter from note metadata.

    Args:
        note: Note dict from database
        processed_at: When markdown was generated (defaults to now)

    Returns:
        YAML frontmatter string including --- delimiters
    """
    if processed_at is None:
        processed_at = datetime.now()

    # Parse created date from file_modified_at
    created = note.get("file_modified_at", "")[:10]  # ISO date portion

    frontmatter = f"""---
created: {created}
processed: {processed_at.strftime('%Y-%m-%d')}
tags: []
source_file: {note['file_path']}
---
"""
    return frontmatter
```

### Step 8.3: Content Assembly

```python
def build_markdown(
    note: dict,
    extracted_text: str,
    processed_at: datetime | None = None,
) -> str:
    """
    Build complete markdown file content.

    Args:
        note: Note dict from database
        extracted_text: Raw or edited text from extractions
        processed_at: When markdown was generated

    Returns:
        Complete markdown content with frontmatter + processed text
    """
    frontmatter = build_frontmatter(note, processed_at)
    processed_text = process_line_breaks(extracted_text)
    return frontmatter + "\n" + processed_text
```

### Step 8.4: File Writer

```python
from pathlib import Path
from app.config import Settings, get_settings
from app.database import get_note_by_id, get_aggregated_text

def save_markdown(
    note_id: int,
    output_path: Path | None = None,
    settings: Settings | None = None,
) -> Path:
    """
    Build and save markdown for a note.

    Args:
        note_id: Database ID of the note
        output_path: Override output path (uses calculated path from note if None)
        settings: Application settings

    Returns:
        Path to the written markdown file

    Raises:
        ValueError: If note not found
    """
    if settings is None:
        settings = get_settings()

    note = get_note_by_id(note_id)
    if note is None:
        raise ValueError(f"Note with id {note_id} not found")

    # Get aggregated text (uses edited_text where available)
    text = get_aggregated_text(note_id, use_edited=True)

    # Build markdown content
    content = build_markdown(note, text)

    # Determine output path
    if output_path is None:
        output_path = _calculate_output_path(note, settings)

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write file
    output_path.write_text(content, encoding='utf-8')

    return output_path
```

### Step 8.5: Handling Edited Text (Critical Design Decision)

**The Problem:**
- `get_aggregated_text()` reads per-page from the `extractions` table
- For multi-page notes, if we store the full edited text in page 0 but leave pages 1..N untouched, `get_aggregated_text` will:
  - Return page 0's `edited_text` (full edited content)
  - Return pages 1..N's `raw_text` (since their `edited_text` is NULL)
  - **Result: Duplicated content!**

**Solution: Two Editing Flows**

#### Flow A: Per-Page Editing (Primary - used by Review UI)
The Review UI shows one page at a time with its PNG + text. As the user navigates:
1. User edits text for page 0 → UI calls `update_extraction_text(ext_id, new_text)`
2. User navigates to page 1, edits → UI calls `update_extraction_text(ext_id, new_text)`
3. When user clicks "Approve" → call `approve_and_save_note(note_id)` with NO `edited_text` param
4. `get_aggregated_text(use_edited=True)` correctly aggregates per-page edits

**No changes needed to `get_aggregated_text`** - it already handles this correctly.

#### Flow B: Full-Text Editing (For single-page notes or simplified UI)
For cases where all text is shown in one text area:
1. User edits the combined text
2. Before approval, call new helper `save_full_text_edit(note_id, edited_text)`
3. This helper:
   - Stores full text in page 0's `edited_text`
   - Deletes extractions for pages 1..N to prevent duplication
4. Then call `approve_and_save_note(note_id)`

### Step 8.5a: Full-Text Edit Helper

```python
from app.database import (
    get_extractions_for_note,
    update_extraction_text,
    get_connection,
)

def save_full_text_edit(note_id: int, edited_text: str) -> None:
    """
    Save a full-text edit for a note, handling multi-page cleanup.

    This is used when the UI presents all text in a single text area
    (e.g., for single-page notes or a simplified review UI).

    For multi-page notes, this:
    1. Stores the full edited text in page 0's edited_text
    2. Deletes extractions for pages 1..N to prevent duplication

    Args:
        note_id: Database ID of the note
        edited_text: The full edited text content

    Raises:
        ValueError: If note has no extractions
    """
    extractions = get_extractions_for_note(note_id)

    if not extractions:
        raise ValueError(f"No extractions found for note {note_id}")

    # Update page 0 with full edited text
    first_extraction_id = extractions[0]["id"]
    update_extraction_text(first_extraction_id, edited_text)

    # Delete other extractions to prevent duplication in aggregation
    if len(extractions) > 1:
        other_ids = [ext["id"] for ext in extractions[1:]]
        with get_connection() as conn:
            placeholders = ",".join("?" * len(other_ids))
            conn.execute(
                f"DELETE FROM extractions WHERE id IN ({placeholders})",
                other_ids,
            )
```

### Step 8.5b: Approval Helper (Simplified)

```python
from app.database import mark_note_approved

def approve_and_save_note(
    note_id: int,
    settings: Settings | None = None,
) -> Path:
    """
    Approve a note and save its markdown file.

    IMPORTANT: If the user has made edits, ensure they are saved to the
    database BEFORE calling this function:
    - Per-page edits: Use update_extraction_text() for each page
    - Full-text edits: Use save_full_text_edit() first

    Args:
        note_id: Database ID of the note
        settings: Application settings

    Returns:
        Path to the written markdown file
    """
    if settings is None:
        settings = get_settings()

    # Save markdown (uses get_aggregated_text which reads from database)
    output_path = save_markdown(note_id, settings=settings)

    # Update database status
    mark_note_approved(note_id, str(output_path))

    return output_path
```

### Step 8.5c: Convenience Wrapper (Optional)

For cases where the caller has both the edited text and wants to approve in one call:

```python
def approve_with_full_text_edit(
    note_id: int,
    edited_text: str,
    settings: Settings | None = None,
) -> Path:
    """
    Save full-text edit and approve in one step.

    Convenience wrapper that combines save_full_text_edit + approve_and_save_note.
    Use this for single-page notes or simplified UIs with one text area.

    Args:
        note_id: Database ID of the note
        edited_text: The full edited text content
        settings: Application settings

    Returns:
        Path to the written markdown file
    """
    save_full_text_edit(note_id, edited_text)
    return approve_and_save_note(note_id, settings=settings)
```

### Step 8.6: Update Processor Integration

Modify `process_single_note()` in `processor.py` to actually write files:

```python
# In the auto-approve branch:
if char_count >= settings.auto_approve_threshold:
    # Import and use markdown service
    from app.services.markdown import save_markdown

    # Save markdown file (this actually writes the file now)
    output_path = save_markdown(note_id, settings=settings)

    # Mark as auto-approved
    mark_note_auto_approved(note_id, str(output_path))
```

### Step 8.7: Update __init__.py Exports

```python
# Add to app/services/__init__.py
from app.services.markdown import (
    build_frontmatter,
    build_markdown,
    process_line_breaks,
    save_markdown,
    save_full_text_edit,
    approve_and_save_note,
    approve_with_full_text_edit,
)

__all__ = [
    # ... existing exports ...
    # Markdown
    "build_frontmatter",
    "build_markdown",
    "process_line_breaks",
    "save_markdown",
    "save_full_text_edit",
    "approve_and_save_note",
    "approve_with_full_text_edit",
]
```

---

## Testing Plan

### Unit Tests for Line Processing

```python
# test_markdown.py

def test_join_incomplete_lines():
    """Lines not ending in punctuation should be joined."""
    assert process_line_breaks("Hello\nworld") == "Hello world"

def test_preserve_sentence_endings():
    """Lines ending in punctuation should not be joined."""
    assert process_line_breaks("Hello.\nWorld") == "Hello.\nWorld"

def test_preserve_empty_lines():
    """Empty lines (paragraphs) should be preserved."""
    result = process_line_breaks("Para 1\n\nPara 2")
    assert "\n\n" in result

def test_preserve_list_items():
    """List items should stay on separate lines."""
    text = "- Item 1\n- Item 2\n- Item 3"
    assert process_line_breaks(text) == text

def test_preserve_numbered_list():
    """Numbered lists should stay on separate lines."""
    text = "1. First\n2. Second"
    assert process_line_breaks(text) == text

def test_preserve_headers():
    """Short capitalized lines (headers) should be preserved."""
    text = "INTRODUCTION\nThis is the intro"
    result = process_line_breaks(text)
    assert result.startswith("INTRODUCTION\n")
```

### Integration Test

```python
def test_full_markdown_generation():
    """Test complete markdown generation flow."""
    note = {
        "file_path": "/path/to/20260115_test.note",
        "file_modified_at": "2026-01-15T10:30:00",
        "output_folder": "Journals/Daily/",
        "file_name": "20260115_test.note",
    }

    text = "Hello\nworld\n\n- Item one\n- Item two"

    result = build_markdown(note, text)

    # Check frontmatter
    assert "---" in result
    assert "created: 2026-01-15" in result
    assert "tags: []" in result
    assert "source_file:" in result

    # Check processed text
    assert "Hello world" in result  # Lines joined
    assert "- Item one" in result   # List preserved
```

### Full-Text Edit Test

```python
def test_save_full_text_edit_multi_page():
    """Test that full-text edit handles multi-page cleanup correctly."""
    # Setup: Create note with 3 page extractions
    note_id = create_test_note_with_pages(3)

    # Verify we have 3 extractions
    extractions = get_extractions_for_note(note_id)
    assert len(extractions) == 3

    # Save full-text edit
    save_full_text_edit(note_id, "This is the full edited content")

    # Verify: Only 1 extraction remains
    extractions = get_extractions_for_note(note_id)
    assert len(extractions) == 1
    assert extractions[0]["edited_text"] == "This is the full edited content"

    # Verify aggregation works correctly
    aggregated = get_aggregated_text(note_id, use_edited=True)
    assert aggregated == "This is the full edited content"
```

### Manual Testing

After implementation, test with a real `.note` file:

```python
from app.services.markdown import save_markdown
from app.database import get_pending_notes

# Get a processed note from database
notes = get_pending_notes()  # or get an approved one
note_id = notes[0]["id"]

# Save markdown and inspect output
output_path = save_markdown(note_id)
print(f"Saved to: {output_path}")
print(output_path.read_text())
```

---

## File Changes Summary

| File | Change |
|------|--------|
| `app/services/markdown.py` | Full implementation (currently empty) |
| `app/services/processor.py` | Add `save_markdown()` call in auto-approve path |
| `app/services/__init__.py` | Add markdown exports |

---

## Edge Cases to Handle

1. **Empty text**: If OCR returned empty/minimal text, should still create markdown file
2. **Unicode characters**: Ensure UTF-8 encoding throughout
3. **Existing files**: Overwrite if file already exists (same note re-processed)
4. **Missing directories**: Create output directories as needed
5. **Multi-page notes**: Aggregated text already handles page joining with `\n\n`
6. **Special characters in paths**: Handle Windows/Unix path differences
7. **Full-text edit on multi-page note**: `save_full_text_edit` deletes pages 1..N extractions (destructive but prevents duplication)
8. **Single-page notes**: Both editing flows work identically (no pages to delete)
9. **No extractions**: `save_full_text_edit` raises `ValueError` if note has no extractions

---

## Questions Resolved

- **Frontmatter fields**: created, processed, tags[], source_file
- **Line processing**: Based on plan.md rules (no n8n JSON reference needed)
- **Output path**: Uses existing `_calculate_output_path()` logic from processor.py

---

## Ready for Implementation

This plan is complete and ready for implementation. The markdown service will:
1. Process OCR text with intelligent line break handling
2. Build YAML frontmatter with requested metadata
3. Write markdown files to the correct Journals/ folder
4. Integrate with both auto-approve and manual approval flows
