# Test Plan - Supernote Converter

## Overview

Test-driven development (TDD) approach for key services in the Supernote Converter application. This plan identifies testable components, defines test cases, and provides a testing workflow.

## Why TDD Here?

- **Replacing working system**: n8n workflow already exists - tests codify expected behavior
- **Text processing logic**: Line break handling is complex and error-prone
- **Path routing logic**: Critical that files end up in correct Journals folders
- **Confidence**: Catch regressions early, especially during refactoring

## Testing Strategy

### High-Value TDD Candidates (Write Tests First)

1. **Markdown Service** - Pure text processing, no external dependencies
2. **Scanner Service** - File discovery and date parsing logic
3. **Path Routing** - Critical correctness requirement

### Integration Tests (Write Alongside Code)

4. **Processor Service** - Orchestration layer with mocked dependencies
5. **OCR Service** - Mock HTTP responses, test error handling

### Manual/Visual Tests (Hard to Automate)

6. **Exporter Service** - Visual verification of PNG quality
7. **Streamlit UI** - User interaction flows

---

## Test Infrastructure Needs

### Framework
```bash
pip install pytest pytest-mock pytest-asyncio pytest-cov
```

### Structure
```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_scanner.py          # Scanner service tests
├── test_markdown.py         # Markdown processing tests
├── test_ocr.py              # OCR service tests (mocked)
├── test_processor.py        # Processor integration tests
├── fixtures/
│   ├── sample.note          # Real Supernote file
│   ├── sample_page.png      # Sample PNG export
│   └── expected_outputs/    # Expected markdown outputs
└── mocks/
    └── ollama_responses.json  # Mock OCR responses
```

### Fixtures (conftest.py)
```python
import pytest
from pathlib import Path

@pytest.fixture
def temp_db(tmp_path):
    """Temporary SQLite database for tests."""
    from app.database import init_db
    db_path = tmp_path / "test.db"
    init_db(str(db_path))
    return db_path

@pytest.fixture
def sample_note_path():
    """Path to sample .note file."""
    return Path(__file__).parent / "fixtures" / "sample.note"

@pytest.fixture
def mock_ollama_response():
    """Mock Ollama OCR response."""
    return {
        "model": "qwen3-vl:8b",
        "response": "This is extracted text from the image.",
        "done": True
    }
```

---

## Service-by-Service Test Plan

## 1. Scanner Service (Step 4)

**Testability:** ⭐⭐⭐⭐⭐ (Pure logic, no I/O needed for core functions)

### Test Cases

#### Date Extraction from Filenames
```python
def test_extract_date_from_standard_format():
    # "2026-01-15_Meeting_Notes.note" → datetime(2026, 1, 15)

def test_extract_date_handles_underscores():
    # "2026_01_15_Notes.note" → datetime(2026, 1, 15)

def test_extract_date_returns_none_for_invalid():
    # "invalid_filename.note" → None

def test_extract_date_handles_partial_dates():
    # "2026-01_Meeting.note" → datetime(2026, 1, 1)
```

#### Cutoff Date Filtering
```python
def test_filter_by_cutoff_includes_newer_notes():
    # Note dated 2026-01-20 with cutoff 2026-01-15 → included

def test_filter_by_cutoff_excludes_older_notes():
    # Note dated 2026-01-10 with cutoff 2026-01-15 → excluded

def test_filter_by_cutoff_includes_exact_match():
    # Note dated 2026-01-15 with cutoff 2026-01-15 → included
```

#### Source Folder Categorization
```python
def test_categorize_work_folder():
    # Path contains "/WORK/" → category = "work"

def test_categorize_daily_journal():
    # Path contains "/Daily Journal/" → category = "daily"

def test_categorize_other():
    # Path without special folders → category = "other"
```

#### File Discovery
```python
def test_scan_finds_note_files(tmp_path):
    # Create temp .note files, verify scanner finds them

def test_scan_ignores_non_note_files(tmp_path):
    # Create .txt, .md files, verify scanner ignores them

def test_scan_handles_nested_directories(tmp_path):
    # Create nested structure, verify recursive scan
```

---

## 2. Markdown Service (Step 8)

**Testability:** ⭐⭐⭐⭐⭐ (Pure text transformation)

### Test Cases

#### Line Break Processing (Most Complex)
```python
def test_join_lines_ending_without_punctuation():
    input_text = "This line continues\non the next line"
    expected = "This line continues on the next line"
    assert process_line_breaks(input_text) == expected

def test_preserve_lines_ending_with_period():
    input_text = "First sentence.\nSecond sentence."
    assert process_line_breaks(input_text) == input_text

def test_preserve_lines_ending_with_punctuation():
    # Test: .  !  ?  :  ;

def test_preserve_empty_lines_as_paragraphs():
    input_text = "Paragraph one.\n\nParagraph two."
    assert process_line_breaks(input_text) == input_text

def test_preserve_dash_list_items():
    input_text = "- Item one\n- Item two"
    assert process_line_breaks(input_text) == input_text

def test_preserve_asterisk_list_items():
    input_text = "* Item one\n* Item two"
    assert process_line_breaks(input_text) == input_text

def test_preserve_bullet_list_items():
    input_text = "• Item one\n• Item two"
    assert process_line_breaks(input_text) == input_text

def test_preserve_numbered_list_items():
    input_text = "1. Item one\n2. Item two"
    assert process_line_breaks(input_text) == input_text

def test_preserve_short_capitalized_lines_as_headers():
    # "HEADER\nsome text" → keep separate
    # Threshold: < 50 chars, starts with capital

def test_join_long_capitalized_lines():
    # Long capitalized line (>50 chars) is not a header → join
```

#### Edge Cases
```python
def test_handle_lines_with_only_whitespace():

def test_handle_mixed_list_markers():
    # "- Item\n* Item\n• Item"

def test_handle_indented_text():
    # Preserve indentation for code blocks?
```

#### Frontmatter Generation
```python
def test_generate_frontmatter_with_all_fields():
    note = Note(
        original_filename="2026-01-15_Meeting.note",
        source_path="/WORK/Project/2026-01-15_Meeting.note",
        note_date=datetime(2026, 1, 15)
    )
    frontmatter = generate_frontmatter(note)
    assert "title: Meeting" in frontmatter
    assert "date: 2026-01-15" in frontmatter
    assert "source: /WORK/Project/2026-01-15_Meeting.note" in frontmatter

def test_frontmatter_handles_special_characters():
    # Filename with colons, quotes, etc.
```

#### Output Path Routing
```python
def test_route_work_note_to_work_folder():
    path = "/data/source/WORK/2026-01-15_Meeting.note"
    output = determine_output_folder(path)
    assert output == "/data/output/Work"

def test_route_daily_journal_to_daily_folder():
    path = "/data/source/Daily Journal/2026-01-15.note"
    output = determine_output_folder(path)
    assert output == "/data/output/Daily"

def test_route_other_to_other_folder():
    path = "/data/source/Random/2026-01-15.note"
    output = determine_output_folder(path)
    assert output == "/data/output/Other"
```

#### Full Markdown Assembly
```python
def test_build_complete_markdown():
    # Frontmatter + processed body + proper newlines

def test_markdown_output_matches_expected_format():
    # Use fixture expected_outputs/ for comparison
```

---

## 3. OCR Service (Step 6)

**Testability:** ⭐⭐⭐⭐ (Mock HTTP, test error handling)

### Test Cases

#### Ollama OCR
```python
def test_ocr_ollama_success(mock_httpx):
    # Mock successful response
    mock_httpx.post.return_value.json.return_value = {
        "response": "Extracted text"
    }
    text = ocr_with_ollama(png_path, url, model)
    assert text == "Extracted text"

def test_ocr_ollama_handles_timeout(mock_httpx):
    mock_httpx.post.side_effect = httpx.TimeoutException
    text = ocr_with_ollama(png_path, url, model)
    assert text is None

def test_ocr_ollama_handles_connection_error(mock_httpx):
    mock_httpx.post.side_effect = httpx.ConnectError
    text = ocr_with_ollama(png_path, url, model)
    assert text is None

def test_ocr_ollama_encodes_image_as_base64(mock_httpx):
    ocr_with_ollama(png_path, url, model)
    call_args = mock_httpx.post.call_args
    assert "images" in call_args[1]["json"]
    # Verify base64 encoding
```

#### OpenAI OCR (Fallback)
```python
def test_ocr_openai_success(mock_httpx):
    # Mock OpenAI API response

def test_ocr_openai_handles_api_error():
    # 429, 500, etc.

def test_ocr_openai_handles_missing_api_key():
    # Should fail gracefully
```

#### OCR Selection Logic
```python
def test_fallback_to_openai_when_ollama_fails():
    # Ollama times out → try OpenAI

def test_respect_user_preference_for_primary_ocr():
    # Settings specify OpenAI first → use that
```

---

## 4. Processor Service (Step 7)

**Testability:** ⭐⭐⭐ (Integration test with mocked services)

### Test Cases

#### Auto-Approve Logic
```python
def test_auto_approve_high_confidence_extraction(mock_ocr, mock_exporter):
    # OCR returns >200 chars → status = 'approved'
    mock_ocr.return_value = "x" * 250
    processor.process_note(note_id)
    note = get_note_by_id(note_id)
    assert note.status == "approved"

def test_review_queue_low_confidence_extraction(mock_ocr, mock_exporter):
    # OCR returns <200 chars → status = 'review'
    mock_ocr.return_value = "short text"
    processor.process_note(note_id)
    note = get_note_by_id(note_id)
    assert note.status == "review"
```

#### Multi-Page Aggregation
```python
def test_aggregate_text_from_multiple_pages(mock_exporter):
    # 3 pages → 3 extraction records → aggregated text
    mock_exporter.return_value = [page1_png, page2_png, page3_png]
    # Verify all pages processed and combined
```

#### Error Handling
```python
def test_mark_note_error_when_export_fails(mock_exporter):
    mock_exporter.side_effect = Exception("Export failed")
    processor.process_note(note_id)
    note = get_note_by_id(note_id)
    assert note.status == "error"

def test_continue_processing_other_notes_after_error():
    # One note fails → others still process
```

---

## 5. Database Layer (Already Implemented)

### Regression Tests (Optional)
```python
def test_database_schema_matches_expected():
    # Verify tables exist

def test_concurrent_access(tmp_path):
    # SQLite threading behavior

def test_migrations_are_idempotent():
    # Run init_db twice → no errors
```

---

## 6. Exporter Service (Step 5)

**Testability:** ⭐⭐ (Requires real .note files, visual verification)

### Test Cases

```python
def test_export_single_page_note(sample_note_path, tmp_path):
    # Export generates 1 PNG
    pngs = export_note_to_png(sample_note_path, tmp_path)
    assert len(pngs) == 1
    assert pngs[0].exists()

def test_export_multi_page_note(multi_page_note_path, tmp_path):
    # Export generates N PNGs
    pngs = export_note_to_png(multi_page_note_path, tmp_path)
    assert len(pngs) > 1

def test_export_handles_corrupted_note():
    # Invalid .note file → raises exception

def test_png_filenames_follow_convention():
    # basename_0.png, basename_1.png, etc.
```

**Note:** Quality of PNGs requires manual visual inspection.

---

## Testing Workflow

### Phase 1: Setup (One-Time)
1. Install pytest and dependencies
2. Create `tests/` directory structure
3. Set up fixtures (sample .note file, expected outputs)
4. Create `conftest.py` with shared fixtures

### Phase 2: TDD Implementation Order

#### Step 2.1: Markdown Service (Pure Logic)
```bash
# Write tests first
tests/test_markdown.py → All test cases for line processing, routing, frontmatter

# Run tests (all fail)
pytest tests/test_markdown.py

# Implement service
app/services/markdown.py

# Run tests (all pass)
pytest tests/test_markdown.py
```

#### Step 2.2: Scanner Service
```bash
# Write tests
tests/test_scanner.py

# Implement
app/services/scanner.py

# Verify
pytest tests/test_scanner.py
```

#### Step 2.3: OCR Service (With Mocks)
```bash
# Write tests with mocked HTTP
tests/test_ocr.py

# Implement
app/services/ocr.py

# Verify
pytest tests/test_ocr.py
```

#### Step 2.4: Integration Tests
```bash
# Write processor tests
tests/test_processor.py

# Implement
app/services/processor.py

# Run full test suite
pytest tests/
```

### Phase 3: Continuous Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_markdown.py

# Run specific test
pytest tests/test_markdown.py::test_preserve_list_items
```

---

## Test Data Fixtures

### Required Sample Files

1. **sample.note** - Single-page Supernote file
2. **multi_page.note** - 3+ page note for pagination testing
3. **work_note.note** - Note with "/WORK/" in path
4. **daily_note.note** - Note with "/Daily Journal/" in path
5. **complex_text.txt** - Sample OCR output with:
   - Paragraphs
   - List items (multiple markers)
   - Headers
   - Incomplete sentences
   - Mixed punctuation

### Expected Outputs

```
tests/fixtures/expected_outputs/
├── sample_processed.md        # Expected output for sample.note
├── work_note_processed.md     # Expected output routed to Work/
└── complex_text_processed.md  # Expected line-processed text
```

---

## Success Criteria

### Test Coverage Goals
- **Markdown service:** >90% coverage (most critical)
- **Scanner service:** >85% coverage
- **OCR service:** >80% coverage (focus on error handling)
- **Processor service:** >75% coverage (integration)

### All Tests Pass
- Zero failures before merging to main
- Zero failures before deploying to Unraid

### Regression Prevention
- Add test for any bug discovered in production
- Port n8n behavior as tests before replacing

---

## Benefits of This Approach

1. **Confidence:** Know the app works before running on real notes
2. **Documentation:** Tests show how each component should behave
3. **Refactoring:** Change implementation safely
4. **Regression Prevention:** Catch bugs early
5. **n8n Parity:** Codify expected behavior from existing workflow

---

## Optional: CI/CD Integration

Once tests are written:

```yaml
# .github/workflows/test.yml
name: Test Suite
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r requirements.txt pytest pytest-cov
      - run: pytest --cov=app tests/
```

---

## Next Steps

1. **Immediate:** Write test cases for Markdown service line processing
2. **Before Step 4:** Set up pytest infrastructure
3. **During Step 4-8:** Follow TDD workflow above
4. **Before deployment:** Achieve coverage goals, all tests passing
