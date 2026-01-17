"""Services for the supernote converter application."""
from app.services.exporter import (
    export_note_by_id,
    export_note_to_png,
    get_page_count,
)
from app.services.markdown import (
    approve_and_save_note,
    approve_with_full_text_edit,
    build_frontmatter,
    build_markdown,
    process_line_breaks,
    save_full_text_edit,
    save_markdown,
)
from app.services.ocr import (
    OCRError,
    extract_text_from_image,
    ocr_with_ollama,
    ocr_with_openai,
)
from app.services.processor import (
    BatchProcessResult,
    ProcessResult,
    process_pending_notes,
    process_single_note,
    run_batch_process,
)
from app.services.scanner import (
    calculate_file_hash,
    extract_date_from_filename,
    get_note_date,
    scan_and_insert,
    scan_source_directory,
)

__all__ = [
    # Exporter
    "export_note_by_id",
    "export_note_to_png",
    "get_page_count",
    # Markdown
    "approve_and_save_note",
    "approve_with_full_text_edit",
    "build_frontmatter",
    "build_markdown",
    "process_line_breaks",
    "save_full_text_edit",
    "save_markdown",
    # OCR
    "OCRError",
    "extract_text_from_image",
    "ocr_with_ollama",
    "ocr_with_openai",
    # Processor
    "BatchProcessResult",
    "ProcessResult",
    "process_pending_notes",
    "process_single_note",
    "run_batch_process",
    # Scanner
    "calculate_file_hash",
    "extract_date_from_filename",
    "get_note_date",
    "scan_and_insert",
    "scan_source_directory",
]
