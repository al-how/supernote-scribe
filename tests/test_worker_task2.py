import asyncio
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.database import (
    acquire_processing_lock,
    count_notes_by_status,
    get_connection,
    get_note_by_id,
    insert_note,
)


def test_process_returns_already_running_when_lock_is_held(test_db):
    from app.worker import app

    acquire_processing_lock("existing-worker", stale_minutes=15)

    client = TestClient(app)
    response = client.post("/process")

    assert response.status_code == 202
    assert response.json()["status"] == "already_running"


def test_process_returns_idle_when_scan_finds_no_pending_notes(test_db, monkeypatch):
    from app.worker import app

    monkeypatch.setattr("app.worker.scan_and_insert", lambda cutoff_date=None: (0, 0, 0))

    client = TestClient(app)
    response = client.post("/process")

    assert response.status_code == 202
    assert response.json()["status"] == "idle"


def test_worker_startup_resets_stale_processing_notes(monkeypatch):
    from app.config import Settings
    from app import worker

    calls = []

    monkeypatch.setattr(
        worker,
        "_init_runtime",
        lambda: Settings(lock_stale_minutes=9, watch_enabled=False, schedule_enabled=False),
    )
    monkeypatch.setattr(
        worker,
        "reset_stale_processing_notes",
        lambda stale_minutes: calls.append(stale_minutes),
    )
    monkeypatch.setattr(worker, "start_watcher_and_scheduler", lambda settings: None)

    asyncio.run(worker.startup_runtime())

    assert calls == [9]


def test_process_recovers_stale_processing_note_without_pending_notes(test_db, monkeypatch):
    from app.worker import app, worker_state

    stale_id = insert_note(
        file_path="/notes/stale-processing.note",
        file_name="stale-processing.note",
        file_modified_at="2026-01-01T00:00:00",
        source_folder="Other",
        output_folder="Journals/Other/",
    )
    # Seed the stale timestamp using the app's local-time clock (_now uses
    # datetime.now()), so the comparison against the reset cutoff is timezone
    # consistent. SQLite's datetime('now') is UTC and would break this test in
    # any timezone west of UTC.
    stale_updated_at = (datetime.now() - timedelta(minutes=30)).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE notes
            SET status = 'processing',
                updated_at = ?
            WHERE id = ?
            """,
            (stale_updated_at, stale_id),
        )

    monkeypatch.setattr("app.worker.scan_and_insert", lambda cutoff_date=None: (0, 0, 0))
    monkeypatch.setattr("app.worker._wake_processing_loop", lambda: None)
    worker_state.state = "idle"
    worker_state.wake_requested = False

    client = TestClient(app)
    response = client.post("/process")

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert get_note_by_id(stale_id)["status"] == "pending"


def test_process_coalesces_wake_up_when_local_worker_is_running(test_db):
    from app.worker import app, worker_state

    acquire_processing_lock("active-local-worker", stale_minutes=15)
    worker_state.state = "running"
    worker_state.wake_requested = False
    worker_state.pending_scan_cutoff = None

    try:
        client = TestClient(app)
        response = client.post("/process")
        assert response.status_code == 202
        assert response.json()["status"] == "accepted"
        assert worker_state.wake_requested is True
        assert worker_state.pending_scan_cutoff is not None
    finally:
        worker_state.state = "idle"
        worker_state.wake_requested = False
        worker_state.pending_scan_cutoff = None


def test_process_endpoint_uses_init_app_for_runtime_initialization(test_db, monkeypatch):
    from app.worker import app, worker_state

    calls = []

    monkeypatch.setattr("app.worker.init_app", lambda: calls.append("init_app"))
    monkeypatch.setattr("app.worker.scan_and_insert", lambda cutoff_date=None: (0, 0, 0))
    worker_state.state = "idle"
    worker_state.wake_requested = False

    client = TestClient(app)
    response = client.post("/process")

    assert response.status_code == 202
    assert calls == ["init_app"]


def test_status_returns_counts_and_worker_state_shape(test_db):
    from app.worker import app

    insert_note(
        file_path="/tmp/example.note",
        file_name="example.note",
        file_modified_at="2026-01-01T00:00:00",
        source_folder="Other",
        output_folder="Journals/Other/",
    )

    client = TestClient(app)
    response = client.get("/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["counts"] == count_notes_by_status()
    assert set(payload["worker"].keys()) >= {
        "state",
        "current_note",
        "last_success",
        "last_error",
    }
    assert payload["watcher"]["status"] in {"running", "stopped"}
    assert payload["next_scheduled_run"] is None
    assert "ocr" in payload


def test_health_reports_database_accessible(test_db):
    from app.worker import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
