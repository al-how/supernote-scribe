"""Task 1 database lock and stale processing recovery tests."""

from datetime import datetime, timedelta

from app.database import (
    acquire_processing_lock,
    get_connection,
    get_processing_lock,
    heartbeat_processing_lock,
    insert_note,
    release_processing_lock,
    reset_stale_processing_notes,
)


def _old_timestamp(minutes: int = 30) -> str:
    return (datetime.now() - timedelta(minutes=minutes)).isoformat()


def test_processing_lock_acquire_contended_stale_steal_release_and_heartbeat(test_db):
    assert acquire_processing_lock("owner-a", stale_minutes=15) == "acquired"

    lock = get_processing_lock()
    assert lock is not None
    assert lock["owner"] == "owner-a"
    assert acquire_processing_lock("owner-b", stale_minutes=15) == "already_running"
    assert heartbeat_processing_lock("owner-b") is False
    assert release_processing_lock("owner-b") is False

    assert heartbeat_processing_lock("owner-a") is True
    heartbeat = get_processing_lock()["heartbeat_at"]
    assert heartbeat is not None

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE processing_lock
            SET heartbeat_at = ?, locked_at = ?
            WHERE id = 1
            """,
            (_old_timestamp(), _old_timestamp()),
        )

    assert acquire_processing_lock("owner-b", stale_minutes=15) == "stale_stolen"
    assert get_processing_lock()["owner"] == "owner-b"
    assert release_processing_lock("owner-a") is False
    assert release_processing_lock("owner-b") is True
    assert get_processing_lock() is None


def test_reset_stale_processing_notes_returns_only_old_processing_notes(test_db):
    fresh_id = insert_note(
        file_path="/notes/fresh.note",
        file_name="fresh.note",
        file_modified_at="2026-01-01T00:00:00",
        source_folder="Other",
        output_folder="Journals/Other/",
    )
    stale_id = insert_note(
        file_path="/notes/stale.note",
        file_name="stale.note",
        file_modified_at="2026-01-01T00:00:00",
        source_folder="Other",
        output_folder="Journals/Other/",
    )
    approved_id = insert_note(
        file_path="/notes/approved.note",
        file_name="approved.note",
        file_modified_at="2026-01-01T00:00:00",
        source_folder="Other",
        output_folder="Journals/Other/",
    )

    with get_connection() as conn:
        conn.execute(
            "UPDATE notes SET status = 'processing', updated_at = ? WHERE id = ?",
            (_old_timestamp(30), stale_id),
        )
        conn.execute(
            "UPDATE notes SET status = 'processing', updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), fresh_id),
        )
        conn.execute(
            "UPDATE notes SET status = 'approved', updated_at = ? WHERE id = ?",
            (_old_timestamp(30), approved_id),
        )

    assert reset_stale_processing_notes(stale_minutes=15) == 1

    with get_connection() as conn:
        rows = conn.execute("SELECT id, status FROM notes").fetchall()
        statuses = {row["id"]: row["status"] for row in rows}

    assert statuses[stale_id] == "pending"
    assert statuses[fresh_id] == "processing"
    assert statuses[approved_id] == "approved"
