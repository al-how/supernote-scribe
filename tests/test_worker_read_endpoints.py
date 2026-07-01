"""Tests for the worker read-cluster GET endpoints."""

from fastapi.testclient import TestClient

from app.database import (
    insert_extraction,
    insert_note,
    log_activity,
    update_note_status,
)


def _seed_note(
    file_path: str,
    file_name: str,
    modified_at: str,
    status: str = "pending",
    source_folder: str = "Daily Journal",
) -> int:
    note_id = insert_note(
        file_path=file_path,
        file_name=file_name,
        file_modified_at=modified_at,
        source_folder=source_folder,
        output_folder="Journals/Daily",
    )
    if status != "pending":
        update_note_status(note_id, status)
    return note_id


def test_activity_returns_events_and_respects_limit(test_db):
    from app.worker import app

    for i in range(5):
        log_activity("scan", f"event {i}")

    client = TestClient(app)
    response = client.get("/activity", params={"limit": 3})

    assert response.status_code == 200
    activity = response.json()["activity"]
    assert len(activity) == 3
    assert activity[0]["message"] == "event 4"  # most recent first


def test_activity_calls_init_runtime(test_db, monkeypatch):
    from app import worker

    calls = []
    original = worker._init_runtime
    monkeypatch.setattr(
        worker, "_init_runtime", lambda: calls.append(True) or original()
    )

    client = TestClient(worker.app)
    response = client.get("/activity")

    assert response.status_code == 200
    assert calls  # handler invoked runtime init


def test_activity_rejects_out_of_range_limit(test_db):
    from app.worker import app

    client = TestClient(app)
    assert client.get("/activity", params={"limit": 0}).status_code == 422


def test_queue_review_returns_only_review_notes_with_counts(test_db):
    from app.worker import app

    _seed_note("/src/a.note", "a.note", "2026-01-01", status="pending")
    review_id = _seed_note("/src/b.note", "b.note", "2026-01-02", status="review")

    client = TestClient(app)
    response = client.get("/queue/review")

    assert response.status_code == 200
    body = response.json()
    assert [n["id"] for n in body["notes"]] == [review_id]
    assert body["counts"]["review"] == 1
    assert body["counts"]["pending"] == 1


def test_notes_filters_and_paginates(test_db):
    from app.worker import app

    _seed_note("/src/keep.note", "keep.note", "2026-01-03", status="approved")
    _seed_note("/src/other.note", "other.note", "2026-01-02", status="pending")

    client = TestClient(app)

    # status filter
    approved = client.get("/notes", params={"status": "approved"}).json()["notes"]
    assert [n["file_name"] for n in approved] == ["keep.note"]

    # search filter
    searched = client.get("/notes", params={"search": "other"}).json()["notes"]
    assert [n["file_name"] for n in searched] == ["other.note"]

    # pagination
    page = client.get("/notes", params={"limit": 1, "offset": 0}).json()["notes"]
    assert len(page) == 1


def test_notes_rejects_out_of_range_limit(test_db):
    from app.worker import app

    client = TestClient(app)
    assert client.get("/notes", params={"limit": 0}).status_code == 422


def test_note_detail_returns_note_with_extractions(test_db):
    from app.worker import app

    note_id = _seed_note("/src/detail.note", "detail.note", "2026-01-04")
    insert_extraction(note_id, page_number=1, raw_text="hello", ai_model="test")

    client = TestClient(app)
    response = client.get(f"/notes/{note_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["note"]["id"] == note_id
    assert body["extractions"][0]["raw_text"] == "hello"


def test_note_detail_returns_404_for_missing_note(test_db):
    from app.worker import app

    client = TestClient(app)
    assert client.get("/notes/999999").status_code == 404
