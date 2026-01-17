"""Services for the supernote converter application."""
from app.services.exporter import (
    export_note_by_id,
    export_note_to_png,
    get_page_count,
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
