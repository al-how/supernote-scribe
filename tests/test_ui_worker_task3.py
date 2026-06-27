from pathlib import Path

import httpx
from fastapi.testclient import TestClient


def test_trigger_worker_process_reports_accepted_response():
    from app.ui_worker import trigger_worker_process

    def post(url: str, timeout: float):
        assert url == "http://worker/process"
        assert timeout == 2.0
        return httpx.Response(
            202,
            json={
                "status": "accepted",
                "message": "Processing 2 note(s) in background",
                "pending_count": 2,
            },
        )

    result = trigger_worker_process("http://worker", post=post)

    assert result.available is True
    assert result.status == "accepted"
    assert result.message == "Processing 2 note(s) in background"


def test_trigger_worker_process_reports_already_running_response():
    from app.ui_worker import trigger_worker_process

    def post(url: str, timeout: float):
        return httpx.Response(
            202,
            json={"status": "already_running", "message": "Processing is already running"},
        )

    result = trigger_worker_process("http://worker", post=post)

    assert result.available is True
    assert result.status == "already_running"
    assert "already running" in result.message


def test_trigger_worker_process_reports_unavailable_when_worker_cannot_be_reached():
    from app.ui_worker import trigger_worker_process

    def post(url: str, timeout: float):
        raise httpx.ConnectError("connection refused")

    result = trigger_worker_process("http://worker", post=post)

    assert result.available is False
    assert result.status == "unavailable"
    assert "Worker is unavailable" in result.message


def test_format_worker_status_marks_unavailable_without_ready_claim():
    from app.ui_worker import WorkerStatusResult, format_worker_status

    formatted = format_worker_status(
        WorkerStatusResult(
            available=False,
            payload=None,
            error="connection refused",
        )
    )

    assert formatted["available"] is False
    assert formatted["label"] == "Worker unavailable"
    assert formatted["state"] == "error"
    assert "not processing" not in formatted["summary"].lower()


def test_format_worker_status_uses_expanded_status_payload():
    from app.ui_worker import WorkerStatusResult, format_worker_status

    formatted = format_worker_status(
        WorkerStatusResult(
            available=True,
            payload={
                "counts": {"pending": 3, "review": 1, "auto_approved": 5},
                "worker": {
                    "state": "running",
                    "current_note": {"file_name": "Daily.note"},
                    "last_success": "2026-06-27T10:00:00",
                    "last_error": None,
                },
                "watcher": {"status": "not_configured", "enabled": True},
                "next_scheduled_run": None,
                "ocr": {"provider": "llama_server", "reachable": None, "message": "not checked"},
            },
        )
    )

    assert formatted["available"] is True
    assert formatted["label"] == "Worker running"
    assert formatted["state"] == "running"
    assert formatted["pending_count"] == 3
    assert formatted["current_note"] == "Daily.note"
    assert formatted["ocr_provider"] == "llama_server"


def test_docker_healthcheck_checks_streamlit_and_worker():
    dockerfile = Path("Dockerfile").read_text()

    assert "localhost:8501/_stcore/health" in dockerfile
    assert "localhost:8000/health" in dockerfile
    assert "&&" in dockerfile or "sh -c" in dockerfile


def test_worker_health_returns_503_when_database_check_fails(monkeypatch):
    from app import worker

    def broken_count_notes_by_status():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(worker, "count_notes_by_status", broken_count_notes_by_status)

    response = TestClient(worker.app).get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "error"
    assert response.json()["database"] == "unavailable"
