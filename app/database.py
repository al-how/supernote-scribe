"""
SQLite database layer for Supernote Converter.

Provides:
- Thread-safe connection management
- Schema migrations
- CRUD operations for notes, extractions, settings, and activity log

Usage:
    from app.database import init_db, get_connection, get_pending_notes

    # On app startup
    init_db()

    # In your code
    notes = get_pending_notes()
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Callable, Generator

# =============================================================================
# Configuration
# =============================================================================

DEFAULT_DB_PATH = Path("data/supernote.db")

# Thread-local storage for connections
_local = threading.local()

# Module-level db path (can be overridden)
_db_path: Path | None = None


def set_db_path(path: Path) -> None:
    """Set the database path. Call before init_db()."""
    global _db_path
    _db_path = path


def get_db_path() -> Path:
    """Get database path from config or default."""
    if _db_path is not None:
        return _db_path
    return DEFAULT_DB_PATH


# =============================================================================
# Connection Management
# =============================================================================


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Get a thread-local database connection.

    Uses WAL mode for better concurrency and Row factory for dict-like access.
    Connection is committed on success, rolled back on exception.

    Usage:
        with get_connection() as conn:
            cursor = conn.execute("SELECT * FROM notes")
            rows = cursor.fetchall()
    """
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Check for existing thread-local connection
    if not hasattr(_local, "connection") or _local.connection is None:
        _local.connection = sqlite3.connect(
            str(db_path),
            check_same_thread=False,  # Allow use across Streamlit threads
            timeout=30.0,
        )
        _local.connection.row_factory = sqlite3.Row  # Dict-like access
        _local.connection.execute("PRAGMA foreign_keys = ON")
        _local.connection.execute("PRAGMA journal_mode = WAL")

    try:
        yield _local.connection
    except Exception:
        _local.connection.rollback()
        raise
    else:
        _local.connection.commit()


def close_connection() -> None:
    """Close the thread-local connection if it exists."""
    if hasattr(_local, "connection") and _local.connection is not None:
        _local.connection.close()
        _local.connection = None


# =============================================================================
# Helper Functions
# =============================================================================


def _now() -> str:
    """Get current timestamp as ISO 8601 string."""
    return datetime.now().isoformat()


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    """Convert sqlite3.Row to dict."""
    if row is None:
        return None
    return dict(row)


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    """Convert list of sqlite3.Row to list of dicts."""
    return [dict(row) for row in rows]


# =============================================================================
# Migration System
# =============================================================================


def _migration_001_initial(conn: sqlite3.Connection) -> None:
    """Initial schema: notes, extractions, settings, activity_log tables."""
    conn.executescript("""
        -- Notes table: track discovered .note files
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL UNIQUE,
            file_name TEXT NOT NULL,
            file_hash TEXT,
            file_modified_at TEXT NOT NULL,
            file_size_bytes INTEGER,
            source_folder TEXT NOT NULL,
            output_folder TEXT NOT NULL,
            page_count INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            error_message TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            processed_at TEXT,
            approved_at TEXT,
            output_path TEXT
        );

        -- Extractions table: OCR results per page
        CREATE TABLE IF NOT EXISTS extractions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            page_number INTEGER NOT NULL,
            png_cache_path TEXT,
            raw_text TEXT,
            edited_text TEXT,
            char_count INTEGER DEFAULT 0,
            ai_model TEXT NOT NULL,
            ai_response_time_ms INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
            UNIQUE(note_id, page_number)
        );

        -- Settings table: persistent configuration
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Activity log: audit trail for dashboard
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            note_id INTEGER,
            message TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE SET NULL
        );

        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_notes_status ON notes(status);
        CREATE INDEX IF NOT EXISTS idx_notes_file_modified ON notes(file_modified_at);
        CREATE INDEX IF NOT EXISTS idx_notes_source_folder ON notes(source_folder);
        CREATE INDEX IF NOT EXISTS idx_extractions_note_id ON extractions(note_id);
        CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at);
        CREATE INDEX IF NOT EXISTS idx_activity_type ON activity_log(event_type);
    """)


# Migration registry: version -> (description, function)
MIGRATIONS: dict[int, tuple[str, Callable[[sqlite3.Connection], None]]] = {
    1: ("Initial schema", _migration_001_initial),
}


def _ensure_schema_version_table(conn: sqlite3.Connection) -> None:
    """Create schema_version table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now')),
            description TEXT
        )
    """)


def _get_current_version(conn: sqlite3.Connection) -> int:
    """Get current schema version, 0 if no migrations applied."""
    _ensure_schema_version_table(conn)
    cursor = conn.execute("SELECT MAX(version) FROM schema_version")
    row = cursor.fetchone()
    return row[0] if row[0] is not None else 0


def _apply_migration(
    conn: sqlite3.Connection,
    version: int,
    description: str,
    func: Callable[[sqlite3.Connection], None],
) -> None:
    """Apply a single migration and record it."""
    func(conn)
    conn.execute(
        "INSERT INTO schema_version (version, description) VALUES (?, ?)",
        (version, description),
    )


def run_migrations(db_path: Path | None = None) -> None:
    """Apply all pending migrations."""
    if db_path is None:
        db_path = get_db_path()

    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), timeout=30.0)
    try:
        current_version = _get_current_version(conn)

        for version in sorted(MIGRATIONS.keys()):
            if version > current_version:
                description, func = MIGRATIONS[version]
                _apply_migration(conn, version, description, func)

        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Initialize database and run migrations. Call on app startup."""
    run_migrations()


# =============================================================================
# Notes CRUD
# =============================================================================


def insert_note(
    file_path: str,
    file_name: str,
    file_modified_at: str,
    source_folder: str,
    output_folder: str,
    file_hash: str | None = None,
    file_size_bytes: int | None = None,
    page_count: int = 0,
) -> int:
    """
    Insert a new note, return its ID.

    Raises sqlite3.IntegrityError if file_path already exists.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO notes (
                file_path, file_name, file_modified_at, source_folder,
                output_folder, file_hash, file_size_bytes, page_count,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_path,
                file_name,
                file_modified_at,
                source_folder,
                output_folder,
                file_hash,
                file_size_bytes,
                page_count,
                _now(),
                _now(),
            ),
        )
        return cursor.lastrowid


def upsert_note(
    file_path: str,
    file_name: str,
    file_modified_at: str,
    source_folder: str,
    output_folder: str,
    file_hash: str | None = None,
    file_size_bytes: int | None = None,
    page_count: int | None = None,
) -> int:
    """
    Insert or update note by file_path, return ID.

    If the note exists and has been modified (different mtime or hash),
    resets status to 'pending' for reprocessing.
    """
    with get_connection() as conn:
        # Check if note exists
        cursor = conn.execute(
            "SELECT id, file_modified_at, file_hash FROM notes WHERE file_path = ?",
            (file_path,),
        )
        existing = cursor.fetchone()

        if existing is None:
            # Insert new note
            cursor = conn.execute(
                """
                INSERT INTO notes (
                    file_path, file_name, file_modified_at, source_folder,
                    output_folder, file_hash, file_size_bytes, page_count,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_path,
                    file_name,
                    file_modified_at,
                    source_folder,
                    output_folder,
                    file_hash,
                    file_size_bytes,
                    page_count or 0,
                    _now(),
                    _now(),
                ),
            )
            return cursor.lastrowid

        note_id = existing["id"]
        old_mtime = existing["file_modified_at"]
        old_hash = existing["file_hash"]

        # Check if file has changed
        file_changed = (
            old_mtime != file_modified_at
            or (file_hash is not None and old_hash != file_hash)
        )

        if file_changed:
            # File changed - update and reset to pending
            update_fields = [
                "file_name = ?",
                "file_modified_at = ?",
                "source_folder = ?",
                "output_folder = ?",
                "file_hash = ?",
                "file_size_bytes = ?",
                "status = 'pending'",
                "error_message = NULL",
                "updated_at = ?",
            ]
            params = [
                file_name,
                file_modified_at,
                source_folder,
                output_folder,
                file_hash,
                file_size_bytes,
                _now(),
                note_id,
            ]

            if page_count is not None:
                update_fields.insert(-2, "page_count = ?")
                params.insert(-2, page_count)

            conn.execute(
                f"UPDATE notes SET {', '.join(update_fields)} WHERE id = ?",
                params,
            )

        return note_id


def get_note_by_id(note_id: int) -> dict | None:
    """Get single note by ID."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        return _row_to_dict(cursor.fetchone())


def get_note_by_path(file_path: str) -> dict | None:
    """Get single note by file path."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM notes WHERE file_path = ?", (file_path,))
        return _row_to_dict(cursor.fetchone())


def get_notes_by_status(status: str | list[str]) -> list[dict]:
    """Get all notes with given status(es)."""
    if isinstance(status, str):
        status = [status]

    placeholders = ", ".join("?" * len(status))
    with get_connection() as conn:
        cursor = conn.execute(
            f"SELECT * FROM notes WHERE status IN ({placeholders}) ORDER BY file_modified_at DESC",
            status,
        )
        return _rows_to_dicts(cursor.fetchall())


def get_pending_notes() -> list[dict]:
    """Get notes with 'pending' status, ordered by modification date."""
    return get_notes_by_status("pending")


def get_review_queue() -> list[dict]:
    """Get notes needing review, ordered by date."""
    return get_notes_by_status("review")


def get_notes_history(
    status_filter: list[str] | None = None,
    source_filter: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search_term: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Get notes with filtering and pagination for History page."""
    conditions = []
    params = []

    if status_filter:
        placeholders = ", ".join("?" * len(status_filter))
        conditions.append(f"status IN ({placeholders})")
        params.extend(status_filter)

    if source_filter:
        conditions.append("source_folder = ?")
        params.append(source_filter)

    if date_from:
        conditions.append("file_modified_at >= ?")
        params.append(date_from)

    if date_to:
        conditions.append("file_modified_at <= ?")
        params.append(date_to)

    if search_term:
        conditions.append("(file_name LIKE ? OR file_path LIKE ?)")
        params.extend([f"%{search_term}%", f"%{search_term}%"])

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    with get_connection() as conn:
        cursor = conn.execute(
            f"""
            SELECT * FROM notes
            WHERE {where_clause}
            ORDER BY file_modified_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        )
        return _rows_to_dicts(cursor.fetchall())


def count_notes_by_status() -> dict[str, int]:
    """Return dict like {'pending': 5, 'review': 3, ...} for Dashboard."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT status, COUNT(*) as count FROM notes GROUP BY status"
        )
        return {row["status"]: row["count"] for row in cursor.fetchall()}


def update_note_status(
    note_id: int, status: str, error_message: str | None = None
) -> None:
    """Update note status and timestamp."""
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE notes SET status = ?, error_message = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, error_message, _now(), note_id),
        )


def mark_note_processing(note_id: int) -> None:
    """Set status to 'processing'."""
    update_note_status(note_id, "processing")


def mark_note_for_review(note_id: int) -> None:
    """Set status to 'review' and record processed_at."""
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE notes SET status = 'review', processed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (_now(), _now(), note_id),
        )


def mark_note_auto_approved(note_id: int, output_path: str) -> None:
    """Set status to 'auto_approved' with output path."""
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE notes SET
                status = 'auto_approved',
                output_path = ?,
                processed_at = ?,
                approved_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (output_path, now, now, now, note_id),
        )


def mark_note_approved(note_id: int, output_path: str) -> None:
    """Set status to 'approved' with output path."""
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE notes SET
                status = 'approved',
                output_path = ?,
                approved_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (output_path, now, now, note_id),
        )


def mark_note_error(note_id: int, error_message: str) -> None:
    """Set status to 'error' with message."""
    update_note_status(note_id, "error", error_message)


def mark_note_rejected(note_id: int) -> None:
    """Set status to 'rejected' - removes from queue but keeps record."""
    update_note_status(note_id, "rejected")


def move_note_to_review(note_id: int) -> None:
    """Move a rejected or approved note back to review queue."""
    update_note_status(note_id, "review")


def update_note_page_count(note_id: int, page_count: int) -> None:
    """Update page count after PNG export."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE notes SET page_count = ?, updated_at = ? WHERE id = ?",
            (page_count, _now(), note_id),
        )


def delete_note(note_id: int) -> None:
    """Delete note and cascade to extractions."""
    with get_connection() as conn:
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))


def reset_note_for_reprocessing(note_id: int) -> None:
    """Reset note to pending, delete its extractions."""
    with get_connection() as conn:
        conn.execute("DELETE FROM extractions WHERE note_id = ?", (note_id,))
        conn.execute(
            """
            UPDATE notes SET
                status = 'pending',
                error_message = NULL,
                processed_at = NULL,
                approved_at = NULL,
                output_path = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (_now(), note_id),
        )


# =============================================================================
# Extractions CRUD
# =============================================================================


def insert_extraction(
    note_id: int,
    page_number: int,
    raw_text: str,
    ai_model: str,
    png_cache_path: str | None = None,
    ai_response_time_ms: int | None = None,
) -> int:
    """Insert extraction result for a page."""
    char_count = len(raw_text) if raw_text else 0
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO extractions (
                note_id, page_number, raw_text, ai_model,
                png_cache_path, ai_response_time_ms, char_count,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note_id,
                page_number,
                raw_text,
                ai_model,
                png_cache_path,
                ai_response_time_ms,
                char_count,
                _now(),
                _now(),
            ),
        )
        return cursor.lastrowid


def get_extractions_for_note(note_id: int) -> list[dict]:
    """Get all extractions for a note, ordered by page number."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM extractions WHERE note_id = ? ORDER BY page_number",
            (note_id,),
        )
        return _rows_to_dicts(cursor.fetchall())


def get_extraction(note_id: int, page_number: int) -> dict | None:
    """Get single extraction by note and page."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM extractions WHERE note_id = ? AND page_number = ?",
            (note_id, page_number),
        )
        return _row_to_dict(cursor.fetchone())


def get_aggregated_text(note_id: int, use_edited: bool = True) -> str:
    """
    Get all text for a note combined.

    If use_edited is True, uses edited_text where available, otherwise raw_text.
    Pages are joined with double newlines.
    """
    extractions = get_extractions_for_note(note_id)
    texts = []
    for ext in extractions:
        if use_edited and ext["edited_text"]:
            texts.append(ext["edited_text"])
        elif ext["raw_text"]:
            texts.append(ext["raw_text"])
    return "\n\n".join(texts)


def update_extraction_text(extraction_id: int, edited_text: str) -> None:
    """Update the edited_text field for review edits."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE extractions SET edited_text = ?, updated_at = ? WHERE id = ?",
            (edited_text, _now(), extraction_id),
        )


def update_extraction_raw_text(
    extraction_id: int, raw_text: str, ai_model: str
) -> None:
    """Update raw_text after re-extraction with different AI."""
    char_count = len(raw_text) if raw_text else 0
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE extractions SET
                raw_text = ?, ai_model = ?, char_count = ?,
                edited_text = NULL, updated_at = ?
            WHERE id = ?
            """,
            (raw_text, ai_model, char_count, _now(), extraction_id),
        )


# =============================================================================
# Settings CRUD
# =============================================================================


def get_setting(key: str, default: str | None = None) -> str | None:
    """Get a setting value."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    """Set a setting value (insert or update)."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
            """,
            (key, value, _now(), value, _now()),
        )


def get_all_settings() -> dict[str, str]:
    """Get all settings as a dict."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT key, value FROM settings")
        return {row["key"]: row["value"] for row in cursor.fetchall()}


def delete_setting(key: str) -> None:
    """Delete a setting by key."""
    with get_connection() as conn:
        conn.execute("DELETE FROM settings WHERE key = ?", (key,))


def clear_all_settings() -> None:
    """Clear all settings from the database."""
    with get_connection() as conn:
        conn.execute("DELETE FROM settings")


# =============================================================================
# Activity Log
# =============================================================================


def log_activity(
    event_type: str,
    message: str,
    note_id: int | None = None,
    details: dict | None = None,
) -> None:
    """Log an activity event."""
    details_json = json.dumps(details) if details else None
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO activity_log (event_type, note_id, message, details, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event_type, note_id, message, details_json, _now()),
        )


def get_recent_activity(limit: int = 20) -> list[dict]:
    """Get recent activity for Dashboard."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM activity_log
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = _rows_to_dicts(cursor.fetchall())
        # Parse JSON details
        for row in rows:
            if row["details"]:
                row["details"] = json.loads(row["details"])
        return rows


# =============================================================================
# Utility Functions
# =============================================================================


def determine_source_folder(file_path: str) -> str:
    """
    Determine source folder type from path.

    Returns: 'WORK', 'Daily Journal', or 'Other'
    """
    # Normalize path separators for comparison
    normalized = file_path.replace("\\", "/")

    if "/WORK/" in normalized:
        return "WORK"
    elif "/Daily Journal/" in normalized:
        return "Daily Journal"
    return "Other"


def determine_output_folder(source_folder: str) -> str:
    """
    Map source folder to output path.

    Returns: 'Journals/Work/', 'Journals/Daily/', or 'Journals/Other/'
    """
    mapping = {
        "WORK": "Journals/Work/",
        "Daily Journal": "Journals/Daily/",
        "Other": "Journals/Other/",
    }
    return mapping.get(source_folder, "Journals/Other/")
