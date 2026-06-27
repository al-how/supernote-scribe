"""Small Streamlit-facing helpers for the FastAPI worker."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

import httpx

DEFAULT_WORKER_URL = os.getenv("WORKER_URL", "http://127.0.0.1:8000").rstrip("/")
WORKER_TIMEOUT_SECONDS = 2.0


@dataclass
class WorkerProcessResult:
    available: bool
    status: str
    message: str
    payload: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class WorkerStatusResult:
    available: bool
    payload: dict[str, Any] | None
    error: str | None = None


PostFunc = Callable[[str, float], httpx.Response]
GetFunc = Callable[[str, float], httpx.Response]


def _default_post(url: str, timeout: float) -> httpx.Response:
    return httpx.post(url, timeout=timeout)


def _default_get(url: str, timeout: float) -> httpx.Response:
    return httpx.get(url, timeout=timeout)


def trigger_worker_process(
    worker_url: str = DEFAULT_WORKER_URL,
    *,
    post: PostFunc = _default_post,
    timeout: float = WORKER_TIMEOUT_SECONDS,
) -> WorkerProcessResult:
    """Ask the worker to scan recent files and process queued notes."""
    url = f"{worker_url.rstrip('/')}/process"
    try:
        response = post(url, timeout)
        if response.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"Worker returned HTTP {response.status_code}",
                request=httpx.Request("POST", url),
                response=response,
            )
        payload = response.json()
    except Exception as exc:
        return WorkerProcessResult(
            available=False,
            status="unavailable",
            message=f"Worker is unavailable at {worker_url}. Start the worker and try again.",
            error=str(exc),
        )

    status = str(payload.get("status", "unknown"))
    message = str(payload.get("message") or _message_for_process_status(status))
    return WorkerProcessResult(available=True, status=status, message=message, payload=payload)


def fetch_worker_status(
    worker_url: str = DEFAULT_WORKER_URL,
    *,
    get: GetFunc = _default_get,
    timeout: float = WORKER_TIMEOUT_SECONDS,
) -> WorkerStatusResult:
    """Fetch the worker's expanded status payload for Streamlit pages."""
    url = f"{worker_url.rstrip('/')}/status"
    try:
        response = get(url, timeout)
        if response.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"Worker returned HTTP {response.status_code}",
                request=httpx.Request("GET", url),
                response=response,
            )
        return WorkerStatusResult(available=True, payload=response.json())
    except Exception as exc:
        return WorkerStatusResult(available=False, payload=None, error=str(exc))


def format_worker_status(result: WorkerStatusResult) -> dict[str, Any]:
    """Normalize worker status for display without hiding unavailable state."""
    if not result.available or result.payload is None:
        return {
            "available": False,
            "label": "Worker unavailable",
            "state": "error",
            "summary": "The background worker could not be reached. Processing cannot start from the web UI.",
            "pending_count": None,
            "review_count": None,
            "processed_count": None,
            "current_note": None,
            "last_success": None,
            "last_error": result.error,
            "watcher_status": None,
            "next_scheduled_run": None,
            "ocr_provider": None,
            "ocr_message": None,
        }

    payload = result.payload
    counts = payload.get("counts", {})
    worker = payload.get("worker", {})
    watcher = payload.get("watcher", {})
    ocr = payload.get("ocr", {})
    state = str(worker.get("state", "unknown"))
    current_note = worker.get("current_note")

    return {
        "available": True,
        "label": f"Worker {state}",
        "state": state,
        "summary": _summary_for_worker_state(state, current_note),
        "pending_count": int(counts.get("pending", 0)),
        "review_count": int(counts.get("review", 0)),
        "processed_count": int(counts.get("approved", 0)) + int(counts.get("auto_approved", 0)),
        "current_note": _current_note_name(current_note),
        "last_success": worker.get("last_success"),
        "last_error": worker.get("last_error"),
        "watcher_status": watcher.get("status"),
        "next_scheduled_run": payload.get("next_scheduled_run"),
        "ocr_provider": ocr.get("provider"),
        "ocr_message": ocr.get("message"),
    }


def _message_for_process_status(status: str) -> str:
    if status == "accepted":
        return "Worker accepted the processing request."
    if status == "already_running":
        return "Processing is already running."
    if status == "idle":
        return "No pending notes to process."
    return f"Worker returned status: {status}"


def _summary_for_worker_state(state: str, current_note: Any) -> str:
    note_name = _current_note_name(current_note)
    if state == "running" and note_name:
        return f"Processing {note_name}"
    if state == "running":
        return "Processing is running."
    if state == "idle":
        return "Worker is reachable and idle."
    return f"Worker state is {state}."


def _current_note_name(current_note: Any) -> str | None:
    if isinstance(current_note, dict):
        return current_note.get("file_name") or current_note.get("file_path")
    if current_note:
        return str(current_note)
    return None
