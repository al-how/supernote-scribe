"""Processor service for orchestrating the main pipeline.

Handles:
- Processing individual notes: PNG export → OCR → database updates
- Batch processing of pending notes
- Auto-approval logic based on character thresholds
- Error handling and activity logging
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Literal

from app.config import get_settings, init_app, Settings
from app.database import (
    get_note_by_id,
    get_pending_notes,
    get_aggregated_text,
    mark_note_processing,
    mark_note_for_review,
    mark_note_auto_approved,
    mark_note_error,
    insert_extraction,
    log_activity,
)
from app.services.exporter import export_note_by_id
from app.services.ocr import extract_text_from_image, OCRError
from app.services.scanner import scan_and_insert

logger = logging.getLogger(__name__)


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class ProcessResult:
    """Result of processing a single note."""

    note_id: int
    status: Literal["auto_approved", "review", "error"]
    page_count: int
    char_count: int
    output_path: str | None
    error_message: str | None = None


@dataclass
class BatchProcessResult:
    """Result of batch processing."""

    scanned: tuple[int, int, int]  # (new, updated, skipped)
    processed: int
    auto_approved: int
    review_queued: int
    errors: int
    error_details: list[tuple[int, str]]  # (note_id, error_message)


# =============================================================================
# Progress Callback Types
# =============================================================================

# (stage, current_page, total_pages) where stage is "exporting", "ocr", "finalizing"
SingleNoteProgressCallback = Callable[[str, int, int], None]

# (stage, current_note, total_notes, note_name) where stage is "processing", "complete"
BatchProgressCallback = Callable[[str, int, int, str], None]


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
# Main Processing Functions
# =============================================================================


def process_single_note(
    note_id: int,
    settings: Settings | None = None,
    progress_callback: SingleNoteProgressCallback | None = None,
    prefer_openai: bool = False,
) -> ProcessResult:
    """
    Process a single note through the full pipeline.

    Pipeline:
    1. Get note from database
    2. Mark as processing
    3. Export PNGs
    4. OCR each page
    5. Get aggregated text
    6. Auto-approve or queue for review
    7. Log activity

    Args:
        note_id: Database ID of note to process
        settings: Application settings (defaults to global settings)
        progress_callback: Optional callback for progress updates
        prefer_openai: If True, use OpenAI as primary OCR

    Returns:
        ProcessResult with status and metadata

    Raises:
        ValueError: If note_id not found in database
    """
    if settings is None:
        settings = get_settings()

    try:
        # 1. Get note from database
        note = get_note_by_id(note_id)
        if note is None:
            raise ValueError(f"Note with id {note_id} not found")

        logger.info(f"Processing note {note_id}: {note['file_name']}")

        # 2. Mark as processing
        mark_note_processing(note_id)

        # 3. Export PNGs
        if progress_callback:
            progress_callback("exporting", 0, 0)

        png_paths = export_note_by_id(note_id)
        page_count = len(png_paths)

        logger.info(f"Exported {page_count} pages for note {note_id}")

        # 4. OCR each page
        for page_num, png_path in enumerate(png_paths):
            if progress_callback:
                progress_callback("ocr", page_num + 1, page_count)

            logger.info(f"OCR page {page_num + 1}/{page_count} for note {note_id}")

            # Extract text with timing
            start_time = time.time()
            try:
                text, provider = extract_text_from_image(
                    png_path, settings, prefer_openai
                )
                time_ms = int((time.time() - start_time) * 1000)

                logger.info(
                    f"OCR succeeded: {len(text)} chars, {provider}, {time_ms}ms"
                )

                # Store extraction
                insert_extraction(
                    note_id=note_id,
                    page_number=page_num,
                    raw_text=text,
                    ai_model=provider,
                    png_cache_path=str(png_path),
                    ai_response_time_ms=time_ms,
                )

            except OCRError as e:
                logger.error(f"OCR failed for page {page_num}: {e}")
                # Insert empty extraction to track failure
                insert_extraction(
                    note_id=note_id,
                    page_number=page_num,
                    raw_text="",
                    ai_model="error",
                    png_cache_path=str(png_path),
                    ai_response_time_ms=None,
                )

        # 5. Get aggregated text
        if progress_callback:
            progress_callback("finalizing", page_count, page_count)

        aggregated_text = get_aggregated_text(note_id)
        char_count = len(aggregated_text)

        logger.info(f"Aggregated text: {char_count} chars for note {note_id}")

        # 6. Auto-approve logic
        if char_count >= settings.auto_approve_threshold:
            # Import markdown service
            from app.services.markdown import save_markdown

            # Save markdown file (this actually writes the file now)
            output_path = save_markdown(note_id, settings=settings)

            # Mark as auto-approved
            mark_note_auto_approved(note_id, str(output_path))

            # Log activity
            log_activity(
                event_type="auto_approved",
                note_id=note_id,
                message=f"Auto-approved: {note['file_name']} ({char_count} chars)",
                details={
                    "page_count": page_count,
                    "char_count": char_count,
                    "output_path": str(output_path),
                },
            )

            logger.info(f"Auto-approved note {note_id}: {char_count} chars")

            return ProcessResult(
                note_id=note_id,
                status="auto_approved",
                page_count=page_count,
                char_count=char_count,
                output_path=str(output_path),
            )
        else:
            # Queue for review
            mark_note_for_review(note_id)

            # Log activity
            log_activity(
                event_type="review_queued",
                note_id=note_id,
                message=f"Queued for review: {note['file_name']} ({char_count} chars)",
                details={
                    "page_count": page_count,
                    "char_count": char_count,
                },
            )

            logger.info(
                f"Queued for review: note {note_id}, {char_count} chars "
                f"(threshold: {settings.auto_approve_threshold})"
            )

            return ProcessResult(
                note_id=note_id,
                status="review",
                page_count=page_count,
                char_count=char_count,
                output_path=None,
            )

    except Exception as e:
        # Error handling: mark note as error
        error_message = str(e)
        logger.error(f"Error processing note {note_id}: {error_message}")

        mark_note_error(note_id, error_message)

        # Log activity
        log_activity(
            event_type="error",
            note_id=note_id,
            message=f"Processing failed: {error_message}",
            details={"error": error_message},
        )

        return ProcessResult(
            note_id=note_id,
            status="error",
            page_count=0,
            char_count=0,
            output_path=None,
            error_message=error_message,
        )


def process_pending_notes(
    settings: Settings | None = None,
    progress_callback: BatchProgressCallback | None = None,
    prefer_openai: bool = False,
) -> BatchProcessResult:
    """
    Process all pending notes in the database.

    Args:
        settings: Application settings (defaults to global settings)
        progress_callback: Optional callback for batch progress updates
        prefer_openai: If True, use OpenAI as primary OCR

    Returns:
        BatchProcessResult with statistics

    Note:
        Individual note failures don't stop batch processing. Errors are
        collected in the result for reporting.
    """
    if settings is None:
        settings = get_settings()

    # Get all pending notes
    pending_notes = get_pending_notes()
    total_notes = len(pending_notes)

    logger.info(f"Processing {total_notes} pending notes")

    # Initialize counters
    processed = 0
    auto_approved = 0
    review_queued = 0
    errors = 0
    error_details: list[tuple[int, str]] = []

    # Process each note
    for idx, note in enumerate(pending_notes):
        note_id = note["id"]
        note_name = note["file_name"]

        if progress_callback:
            progress_callback("processing", idx + 1, total_notes, note_name)

        logger.info(f"Processing note {idx + 1}/{total_notes}: {note_name}")

        # Process the note
        result = process_single_note(
            note_id=note_id,
            settings=settings,
            prefer_openai=prefer_openai,
        )

        # Update counters
        processed += 1

        if result.status == "auto_approved":
            auto_approved += 1
        elif result.status == "review":
            review_queued += 1
        elif result.status == "error":
            errors += 1
            error_details.append((note_id, result.error_message or "Unknown error"))

    if progress_callback:
        progress_callback("complete", total_notes, total_notes, "")

    logger.info(
        f"Batch processing complete: {processed} processed, "
        f"{auto_approved} auto-approved, {review_queued} queued, {errors} errors"
    )

    # Log batch activity
    log_activity(
        event_type="batch_process",
        message=f"Batch processed {processed} notes",
        details={
            "processed": processed,
            "auto_approved": auto_approved,
            "review_queued": review_queued,
            "errors": errors,
        },
    )

    return BatchProcessResult(
        scanned=(0, 0, 0),  # No scan data in this function
        processed=processed,
        auto_approved=auto_approved,
        review_queued=review_queued,
        errors=errors,
        error_details=error_details,
    )


def run_batch_process(
    cutoff_date: date | None = None,
    prefer_openai: bool = False,
) -> BatchProcessResult:
    """
    CLI convenience function: scan + process in one call.

    Initializes the app, scans for notes, then processes all pending notes.

    Args:
        cutoff_date: Optional cutoff date for scanning (only process notes >= this date)
        prefer_openai: If True, use OpenAI as primary OCR

    Returns:
        BatchProcessResult with combined scan and process statistics
    """
    # Initialize app
    settings = init_app()

    logger.info("Starting batch process")
    if cutoff_date:
        logger.info(f"Cutoff date: {cutoff_date}")

    # Scan for notes
    logger.info("Scanning for notes...")
    scanned = scan_and_insert(cutoff_date=cutoff_date)
    logger.info(f"Scan results: new={scanned[0]}, updated={scanned[1]}, skipped={scanned[2]}")

    # Log scan activity
    log_activity(
        event_type="scan",
        message=f"Scanned: {scanned[0]} new, {scanned[1]} updated, {scanned[2]} skipped",
        details={
            "new": scanned[0],
            "updated": scanned[1],
            "skipped": scanned[2],
        },
    )

    # Process pending notes
    logger.info("Processing pending notes...")
    result = process_pending_notes(settings=settings, prefer_openai=prefer_openai)

    # Combine scan results into the batch result
    result.scanned = scanned

    return result
