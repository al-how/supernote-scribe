"""Markdown service for building and saving markdown files.

Handles:
- Line break processing (intelligent joining of OCR text)
- YAML frontmatter generation
- Markdown file assembly
- File writing and approval workflows
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from app.config import Settings, get_settings
from app.database import (
    get_note_by_id,
    get_aggregated_text,
    get_extractions_for_note,
    update_extraction_text,
    mark_note_approved,
    get_connection,
)


def _get_effective_settings() -> Settings:
    """Get settings with database overrides applied."""
    from app.settings_manager import SettingsManager
    return Settings(**SettingsManager().get_all())


# =============================================================================
# Constants
# =============================================================================

# Punctuation that ends a complete thought
SENTENCE_ENDINGS = {'.', '!', '?', ':', ';'}

# Patterns for list items
LIST_PATTERN = re.compile(r'^[\s]*[-*•][\s]|^[\s]*\d+[.)][\s]')

# Pattern for short capitalized lines (headers)
HEADER_PATTERN = re.compile(r'^[A-Z][A-Z\s]{2,}$')


# =============================================================================
# Line Processing Functions
# =============================================================================


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
    """
    Process OCR text to intelligently handle line breaks.

    Rules:
    1. Join lines not ending with sentence-ending punctuation
    2. Preserve empty lines (paragraphs)
    3. Preserve list items (-, *, •, numbered)
    4. Preserve short capitalized lines (headers)

    Args:
        text: Raw OCR text with potentially excessive line breaks

    Returns:
        Processed text with intelligent line break handling
    """
    if not text:
        return text

    lines = text.split('\n')
    result_lines = []
    i = 0

    while i < len(lines):
        current_line = lines[i]

        # Preserve empty lines (paragraph breaks)
        if not current_line.strip():
            result_lines.append(current_line)
            i += 1
            continue

        # Preserve list items
        if _is_list_item(current_line):
            result_lines.append(current_line)
            i += 1
            continue

        # Preserve headers
        if _is_header(current_line):
            result_lines.append(current_line)
            i += 1
            continue

        # Check if line ends with sentence-ending punctuation
        if _ends_sentence(current_line):
            result_lines.append(current_line)
            i += 1
            continue

        # Line doesn't end with sentence-ending punctuation
        # Try to join with next line(s)
        accumulated = current_line
        i += 1

        while i < len(lines):
            next_line = lines[i]

            # Stop if next line is empty (paragraph break)
            if not next_line.strip():
                break

            # Stop if next line is a list item
            if _is_list_item(next_line):
                break

            # Stop if next line is a header
            if _is_header(next_line):
                break

            # Join with space
            accumulated += ' ' + next_line.strip()
            i += 1

            # Stop if accumulated line ends with sentence-ending punctuation
            if _ends_sentence(accumulated):
                break

        result_lines.append(accumulated)

    return '\n'.join(result_lines)


# =============================================================================
# Frontmatter Builder
# =============================================================================


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


# =============================================================================
# Content Assembly
# =============================================================================


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


# =============================================================================
# Helper Functions
# =============================================================================


def _calculate_output_path(note: dict, settings: Settings) -> Path:
    """
    Calculate output path for a note's markdown file.

    Args:
        note: Note dict from database with keys "output_folder" and "file_name"
        settings: Application settings

    Returns:
        Full path to output markdown file
    """
    # output_folder from database: "Journals/Work/", "Journals/Daily/", etc.
    output_folder = note["output_folder"]
    file_name = Path(note["file_name"]).stem + ".md"
    return settings.output_path / output_folder / file_name


# =============================================================================
# File Writer
# =============================================================================


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
        settings = _get_effective_settings()

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


# =============================================================================
# Full-Text Edit Handling
# =============================================================================


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


# =============================================================================
# Approval Helpers
# =============================================================================


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
        settings = _get_effective_settings()

    # Save markdown (uses get_aggregated_text which reads from database)
    output_path = save_markdown(note_id, settings=settings)

    # Update database status
    mark_note_approved(note_id, str(output_path))

    return output_path


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
