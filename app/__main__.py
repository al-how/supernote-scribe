"""CLI entry point for headless processing.

Usage:
    python -m app --process                    # Scan + process all pending
    python -m app --process --cutoff 2026-01-01  # With date filter
    python -m app --scan-only                  # Just scan, don't process
    python -m app --rescan                     # Reset all notes and reprocess
    python -m app --rescan --cutoff 2026-01-01 # Rescan notes on/after date
    python -m app --prefer-openai              # Use OpenAI as primary OCR
    python -m app -v                           # Verbose logging
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from app.services.processor import run_batch_process, process_pending_notes
from app.services.scanner import scan_and_insert, get_note_date
from app.database import init_db, get_all_notes, reset_note_for_reprocessing
from app.config import init_app
from app import __version__


def setup_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_cutoff_date(date_str: str) -> datetime:
    """
    Parse cutoff date string in YYYY-MM-DD format.

    Args:
        date_str: Date string to parse

    Returns:
        datetime.date object

    Raises:
        ValueError: If date string is invalid
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(
            f"Invalid date format: {date_str}. Expected YYYY-MM-DD (e.g., 2026-01-01)"
        )


def rescan_notes(cutoff_date, prefer_openai: bool = False) -> int:
    """Reset notes to pending (filtered by cutoff) and reprocess them."""
    logger = logging.getLogger(__name__)

    init_app()
    init_db()

    all_notes = get_all_notes()

    if cutoff_date is not None:
        notes_to_reset = [
            n for n in all_notes
            if get_note_date(Path(n["file_path"])) >= cutoff_date
        ]
    else:
        notes_to_reset = all_notes

    if not notes_to_reset:
        print("No notes matched the given cutoff. Nothing to rescan.")
        return 0

    logger.info(f"Resetting {len(notes_to_reset)} note(s) to pending...")
    for note in notes_to_reset:
        reset_note_for_reprocessing(note["id"])

    print(f"\n=== Rescan: Reset {len(notes_to_reset)} note(s) ===\n")

    result = process_pending_notes(prefer_openai=prefer_openai)

    print("=== Processing Results ===")
    print(f"Processed: {result.processed}")
    print(f"Auto-approved: {result.auto_approved}")
    print(f"Review queue: {result.review_queued}")
    print(f"Errors: {result.errors}")
    print()

    if result.error_details:
        print("=== Errors ===")
        for note_id, error_msg in result.error_details:
            print(f"Note {note_id}: {error_msg}")
        print()

    return 1 if result.errors > 0 else 0


def main() -> int:
    """
    Main CLI entry point.

    Returns:
        Exit code (0 = success, 1 = errors occurred)
    """
    parser = argparse.ArgumentParser(
        description="Supernote Converter - Process .note files to markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Modes
    parser.add_argument(
        "--process",
        action="store_true",
        help="Scan and process all pending notes (default action)",
    )
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Only scan for new notes, don't process",
    )
    parser.add_argument(
        "--rescan",
        action="store_true",
        help="Reset notes to pending and reprocess (use --cutoff to limit by date)",
    )

    # Options
    parser.add_argument(
        "--cutoff",
        type=str,
        metavar="YYYY-MM-DD",
        help="Only process notes with date >= cutoff (e.g., 2026-01-01)",
    )
    parser.add_argument(
        "--prefer-openai",
        action="store_true",
        help="Use OpenAI as primary OCR instead of Ollama",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program's version number and exit",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Parse cutoff date if provided
    cutoff_date = None
    if args.cutoff:
        try:
            cutoff_date = parse_cutoff_date(args.cutoff)
            logger.info(f"Using cutoff date: {cutoff_date}")
        except ValueError as e:
            logger.error(str(e))
            return 1

    try:
        # Handle rescan mode
        if args.rescan:
            logger.info("Running rescan mode")
            return rescan_notes(cutoff_date, args.prefer_openai)

        # Handle scan-only mode
        if args.scan_only:
            logger.info("Running scan-only mode")
            init_app()
            scanned = scan_and_insert(cutoff_date=cutoff_date)

            print("\n=== Scan Results ===")
            print(f"New: {scanned[0]}")
            print(f"Updated: {scanned[1]}")
            print(f"Skipped: {scanned[2]}")
            print()

            return 0

        # Default: full process mode (scan + process)
        logger.info("Running full process mode (scan + process)")
        result = run_batch_process(
            cutoff_date=cutoff_date,
            prefer_openai=args.prefer_openai,
        )

        # Print results
        print("\n=== Scan Results ===")
        print(f"New: {result.scanned[0]}")
        print(f"Updated: {result.scanned[1]}")
        print(f"Skipped: {result.scanned[2]}")
        print()

        print("=== Processing Results ===")
        print(f"Processed: {result.processed}")
        print(f"Auto-approved: {result.auto_approved}")
        print(f"Review queue: {result.review_queued}")
        print(f"Errors: {result.errors}")
        print()

        # Print error details if any
        if result.error_details:
            print("=== Errors ===")
            for note_id, error_msg in result.error_details:
                print(f"Note {note_id}: {error_msg}")
            print()

        # Return exit code (1 if errors occurred, 0 otherwise)
        return 1 if result.errors > 0 else 0

    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        return 130  # Standard Unix exit code for SIGINT
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
