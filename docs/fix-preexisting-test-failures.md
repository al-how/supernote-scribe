# Fix Pre-existing Test Failures

## Context

6 tests are currently failing. These are pre-existing failures unrelated to the webhook feature added in the previous session. Fix them without changing application behavior.

## Failures

### 1. Fixture count mismatch (2 tests)

```
tests/test_exporter.py::test_export_all_fixtures
  AssertionError: Expected 7 fixtures, found 12

tests/test_scanner.py::test_scan_real_fixtures
  assert 12 == 7
```

The `tests/fixtures/` directory now has 12 `.note` files but the tests hardcode `7`. Either update the expected counts to match reality, or check whether extra fixture files were added unintentionally and should be removed.

### 2. SQLite UNIQUE constraint on `file_path` (1 test)

```
tests/test_exporter.py::test_export_note_by_id_updates_page_count
  sqlite3.IntegrityError: UNIQUE constraint failed: notes.file_path
```

The test calls `insert_note` with a file path that already exists in the DB (likely from a previous test run leaking state). The test needs proper DB isolation — use a fresh in-memory or temp-file SQLite DB, or call the DB setup/teardown fixtures correctly.

### 3. PNG cache directory not created (2 tests)

```
tests/test_exporter.py::test_export_uses_config_path_when_none
  AssertionError: assert False (png_cache path does not exist)

tests/test_exporter.py::test_export_note_by_id_creates_subdirectory
  AssertionError: assert False (png_cache/1 subdirectory does not exist)
```

The exporter is not creating the expected output directories. Likely caused by the same test isolation issue (mock setup or config patching not working correctly), or the exporter code path for directory creation changed. Read the current exporter code and test setup before fixing.

### 4. Scanner ignores config source path (1 test)

```
tests/test_scanner.py::test_scan_and_insert_respects_source_path_from_config
  assert 0 == 1
```

The test expects the scanner to find 1 note using the config's `SOURCE_PATH`, but finds 0. Likely a test setup issue — the patched config path may not be pointing at the right fixture directory, or the scanner is not picking up the patched value.

## Approach

1. Read the failing test files (`tests/test_exporter.py`, `tests/test_scanner.py`) and the relevant source files (`app/exporter.py`, `app/scanner.py`) before making any changes.
2. Fix the simplest issues first (fixture count hardcodes).
3. For the isolation failures, check how other passing tests set up the DB — follow the same pattern.
4. Run `pytest --tb=short -q` after each fix to confirm progress.
5. Do not change application logic — only fix the tests.
