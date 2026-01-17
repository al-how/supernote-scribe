"""Exporter service for converting .note files to PNG."""
from pathlib import Path

from supernotelib import parser
from supernotelib.converter import ImageConverter, build_visibility_overlay

from app.config import get_settings
from app.database import (
    get_note_by_id,
    update_note_page_count,
)


def get_page_count(note_path: Path) -> int:
    """
    Get number of pages in a .note file without exporting.

    Useful for progress tracking before batch export.

    Args:
        note_path: Path to the .note file

    Returns:
        Number of pages in the notebook

    Raises:
        FileNotFoundError: If note_path doesn't exist
        ValueError: If file is not a valid .note file
    """
    if not note_path.exists():
        raise FileNotFoundError(f"Note file not found: {note_path}")

    try:
        notebook = parser.load_notebook(str(note_path))
        return notebook.get_total_pages()
    except Exception as e:
        raise ValueError(f"Invalid .note file: {note_path}: {e}") from e


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
    if not note_path.exists():
        raise FileNotFoundError(f"Note file not found: {note_path}")

    if output_dir is None:
        settings = get_settings()
        output_dir = Path(settings.png_cache_path)

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Load the notebook
        notebook = parser.load_notebook(str(note_path))
        total_pages = notebook.get_total_pages()

        # Create image converter
        image_converter = ImageConverter(notebook)

        # Build default visibility overlay (show all layers)
        visibility = build_visibility_overlay()

        png_paths = []
        for page_num in range(total_pages):
            # Convert page to PIL Image
            pil_image = image_converter.convert(
                page_num,
                visibility_overlay=visibility,
            )

            # Save to PNG with naming convention: {stem}_{page}.png
            png_path = output_dir / f"{note_path.stem}_{page_num}.png"
            pil_image.save(str(png_path), format="PNG")
            png_paths.append(png_path)

        return png_paths

    except FileNotFoundError:
        raise
    except Exception as e:
        raise ValueError(f"Invalid .note file: {note_path}: {e}") from e


def export_note_by_id(note_id: int) -> list[Path]:
    """
    Export note from database by ID, updating page_count.

    Handles:
    - Look up note path from database
    - Create PNG cache subdirectory per note_id
    - Export all pages
    - Update note's page_count in database
    - Return list of PNG paths

    Args:
        note_id: Database ID of the note

    Returns:
        List of paths to exported PNG files

    Raises:
        ValueError: If note_id not found
    """
    # Look up note from database
    note = get_note_by_id(note_id)
    if note is None:
        raise ValueError(f"Note with id {note_id} not found")

    # Get note path
    note_path = Path(note["file_path"])
    if not note_path.exists():
        raise FileNotFoundError(f"Note file not found: {note_path}")

    # Create PNG cache subdirectory using note_id
    settings = get_settings()
    output_dir = Path(settings.png_cache_path) / str(note_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Export to PNG
    png_paths = export_note_to_png(note_path, output_dir)

    # Update page count in database
    update_note_page_count(note_id, len(png_paths))

    return png_paths
