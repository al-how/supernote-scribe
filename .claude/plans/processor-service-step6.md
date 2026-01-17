# Processor Service Implementation Plan

## Overview

Implement the Processor service (Step 7 from `docs/plan.md`) that orchestrates the main pipeline: pending notes → PNG export → OCR per page → database updates → auto-approve or queue for review.

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `app/services/processor.py` | Implement | Main processor service (~150 lines) |
| `app/__main__.py` | Implement | CLI entry point (~80 lines) |
| `app/services/__init__.py` | Update | Add processor + OCR exports |

## Data Structures

```python
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
```

## Processor Service Functions

### 1. `process_single_note(note_id, settings, progress_callback, prefer_openai) -> ProcessResult`

Pipeline:
1. Get note from database via `get_note_by_id(note_id)`
2. Mark as processing: `mark_note_processing(note_id)`
3. Export PNGs: `export_note_by_id(note_id)` → returns list of PNG paths
4. OCR each page:
   - Call `extract_text_from_image(png_path, settings, prefer_openai)`
   - Store via `insert_extraction(note_id, page_num, text, provider, png_path, time_ms)`
5. Get aggregated text: `get_aggregated_text(note_id)`
6. Auto-approve logic:
   - If `len(text) >= settings.auto_approve_threshold` (200 chars):
     - Calculate output_path
     - Call `mark_note_auto_approved(note_id, output_path)`
   - Else: Call `mark_note_for_review(note_id)`
7. Log activity via `log_activity()`

Error handling: Catch exceptions, call `mark_note_error(note_id, message)`, return error result.

### 2. `process_pending_notes(settings, progress_callback, prefer_openai) -> BatchProcessResult`

1. Get all pending notes: `get_pending_notes()`
2. Loop through each, calling `process_single_note()`
3. Collect statistics and errors
4. Individual failures don't stop batch processing

### 3. `run_batch_process(cutoff_date, prefer_openai) -> BatchProcessResult`

CLI convenience function:
1. Call `init_app()` to initialize settings + database
2. Scan: `scan_and_insert(cutoff_date=cutoff_date)`
3. Process: `process_pending_notes()`
4. Return combined results

### Helper: `_calculate_output_path(note, settings) -> Path`

```python
# output_folder from database: "Journals/Work/", "Journals/Daily/", etc.
output_folder = note["output_folder"]
file_name = Path(note["file_name"]).stem + ".md"
return settings.output_path / output_folder / file_name
```

## CLI Entry Point (`__main__.py`)

```bash
python -m app --process                    # Scan + process all pending
python -m app --process --cutoff 2026-01-01  # With date filter
python -m app --scan-only                  # Just scan, don't process
python -m app --prefer-openai              # Use OpenAI as primary OCR
python -m app -v                           # Verbose logging
```

Output format:
```
=== Scan Results ===
New: 3, Updated: 1, Skipped: 10

=== Processing Results ===
Processed: 4
Auto-approved: 3
Review queue: 1
Errors: 0
```

Exit codes: 0 = success, 1 = errors occurred

## Progress Callbacks

For Streamlit UI integration:
- `SingleNoteProgressCallback = Callable[[str, int, int], None]`
  - `(stage, current_page, total_pages)` where stage is "exporting", "ocr", "finalizing"
- `BatchProgressCallback = Callable[[str, int, int, str], None]`
  - `(stage, current_note, total_notes, note_name)` where stage is "processing", "complete"

## Services `__init__.py` Updates

Add exports for both OCR and processor:
```python
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
```

## Integration Points

| Service | Function Used | Purpose |
|---------|--------------|---------|
| Scanner | `scan_and_insert()` | Find new notes in CLI mode |
| Exporter | `export_note_by_id()` | Convert .note to PNGs |
| OCR | `extract_text_from_image()` | Extract text with fallback |
| Database | Multiple functions | Status management, extractions |
| Config | `get_settings()`, `init_app()` | Settings access |

## Error Handling

- Individual note failures don't stop batch processing
- Errors logged to database via `mark_note_error()`
- Activity logged via `log_activity()`
- Collected in `BatchProcessResult.error_details`
- Users can retry failed notes later

## Note on Markdown Service (Step 8)

The processor calculates `output_path` and stores it in the database, but does NOT write the actual markdown file yet. That's Step 8's responsibility. This allows:
1. Testing the full pipeline without markdown output
2. Clean separation of concerns
3. Step 8 will add the actual file writing to `process_single_note()`

## Verification Plan

After implementation, test with:

```bash
# 1. Scan only - verify file discovery works
python -m app --scan-only -v

# 2. Full process with a recent cutoff to limit test scope
python -m app --process --cutoff 2026-01-15 -v

# 3. Check database state
sqlite3 data/supernote.db "SELECT id, file_name, status, page_count FROM notes"
sqlite3 data/supernote.db "SELECT note_id, page_number, char_count, ai_model FROM extractions"

# 4. Check activity log
sqlite3 data/supernote.db "SELECT event_type, message FROM activity_log ORDER BY id DESC LIMIT 10"
```

## Implementation Order

1. Create `processor.py` with dataclasses and helper functions
2. Implement `process_single_note()`
3. Implement `process_pending_notes()`
4. Implement `run_batch_process()`
5. Implement `__main__.py` CLI
6. Update `services/__init__.py` with exports
7. Test with sample .note files
