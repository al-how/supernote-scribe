"""FastAPI worker for lock-aware background processing."""

from __future__ import annotations

import asyncio
import logging
import socket
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Literal

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import Settings, init_app
from app.database import (
    DEFAULT_DB_PATH,
    acquire_processing_lock,
    count_notes_by_status,
    get_pending_notes,
    get_processing_lock,
    get_db_path,
    heartbeat_processing_lock,
    init_db,
    release_processing_lock,
    reset_stale_processing_notes,
    set_db_path,
)
from app.services.processor import BatchProcessResult, process_pending_notes
from app.services.scanner import scan_and_insert
from app.services.notifications import build_notifier
from app.services.watcher import build_note_observer

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 7
ABORT_FILE = Path(".abort_processing")

RunStatus = Literal["accepted", "idle", "already_running", "completed", "error"]


@dataclass
class WorkerRunResult:
    status: RunStatus
    scanned: tuple[int, int, int] = (0, 0, 0)
    result: BatchProcessResult | None = None
    message: str = ""
    error: str | None = None


class WorkerState:
    def __init__(self) -> None:
        self.state = "idle"
        self.current_note: dict | None = None
        self.last_success: str | None = None
        self.last_error: str | None = None
        self.task: asyncio.Task | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.watcher: Any | None = None
        self.scheduler: Any | None = None
        self.wake_requested = False
        self.pending_scan_requested = False
        self.pending_scan_cutoff: date | None = None


worker_state = WorkerState()
app = FastAPI(title="Supernote Worker")


def _get_effective_settings() -> Settings:
    from app.settings_manager import SettingsManager

    return Settings(**SettingsManager().get_all())


def _init_runtime() -> Settings:
    """Initialize settings/DB without clobbering an explicit test DB path."""
    configured_db_path = get_db_path()
    settings = init_app()
    if settings is None:
        settings = _get_effective_settings()
    if configured_db_path != DEFAULT_DB_PATH and configured_db_path != settings.database_path:
        set_db_path(configured_db_path)
        init_db()
    return _get_effective_settings()


def _owner_token(prefix: str = "worker") -> str:
    host = socket.gethostname()
    return f"{prefix}:{host}:{uuid.uuid4().hex}"


def _is_abort_requested() -> bool:
    return ABORT_FILE.exists()


def _is_lock_stale(lock: dict, stale_minutes: int) -> bool:
    heartbeat = lock.get("heartbeat_at") or lock.get("locked_at")
    if not heartbeat:
        return False
    try:
        heartbeat_at = datetime.fromisoformat(heartbeat)
    except ValueError:
        return False
    return heartbeat_at < datetime.now() - timedelta(minutes=stale_minutes)


def _lock_blocks_processing(settings: Settings) -> bool:
    lock = get_processing_lock()
    if lock is None:
        return False
    return not _is_lock_stale(lock, settings.lock_stale_minutes)


def _recent_cutoff() -> date:
    return date.today() - timedelta(days=LOOKBACK_DAYS)


def process_batch_with_lock(
    *,
    scanned: tuple[int, int, int] = (0, 0, 0),
    cutoff_date: date | None = None,
    scan_before_process: bool = True,
    prefer_openai: bool = False,
    owner: str | None = None,
) -> WorkerRunResult:
    """Run scan and processing under the database processing lock."""
    settings = _get_effective_settings()
    notifier = build_notifier(settings)
    owner = owner or _owner_token()
    lock_result = acquire_processing_lock(owner, settings.lock_stale_minutes)

    if lock_result == "already_running":
        return WorkerRunResult(
            status="already_running",
            scanned=scanned,
            message="Processing is already running",
        )

    try:
        reset_stale_processing_notes(settings.lock_stale_minutes)

        if scan_before_process:
            scanned = scan_and_insert(cutoff_date=cutoff_date)

        pending = get_pending_notes()
        if not pending:
            return WorkerRunResult(
                status="idle",
                scanned=scanned,
                message="No files to process",
            )

        notifier.send_start()

        def heartbeat() -> None:
            heartbeat_processing_lock(owner)

        def set_current_note(note: dict | None) -> None:
            worker_state.current_note = note

        result = process_pending_notes(
            settings=settings,
            prefer_openai=prefer_openai,
            abort_check=_is_abort_requested,
            heartbeat_callback=heartbeat,
            current_note_callback=set_current_note,
        )
        result.scanned = scanned
        notifier.send_complete(
            processed=result.processed,
            review_count=result.review_queued,
            errors=result.errors,
        )
        if result.errors:
            notifier.send_error(f"{result.errors} note(s) failed during processing")
        return WorkerRunResult(
            status="completed",
            scanned=scanned,
            result=result,
            message=f"Processed {result.processed} note(s)",
        )
    except Exception as exc:
        logger.exception("Worker processing failed")
        notifier.send_error(str(exc))
        return WorkerRunResult(
            status="error",
            scanned=scanned,
            message="Processing failed",
            error=str(exc),
        )
    finally:
        worker_state.current_note = None
        release_processing_lock(owner)


def run_cli_process(
    *,
    cutoff_date: date | None = None,
    prefer_openai: bool = False,
) -> WorkerRunResult:
    """CLI entry point for the same lock-aware processing path as the worker."""
    settings = _init_runtime()
    if _lock_blocks_processing(settings):
        return WorkerRunResult(
            status="already_running",
            message="Processing is already running",
        )
    return process_batch_with_lock(
        cutoff_date=cutoff_date,
        prefer_openai=prefer_openai,
        owner=_owner_token("cli"),
    )


async def _processing_loop() -> None:
    worker_state.state = "running"
    try:
        while worker_state.wake_requested:
            worker_state.wake_requested = False
            scan_before_process = worker_state.pending_scan_requested
            scan_cutoff = worker_state.pending_scan_cutoff
            worker_state.pending_scan_requested = False
            worker_state.pending_scan_cutoff = None
            result = await asyncio.to_thread(
                process_batch_with_lock,
                cutoff_date=scan_cutoff,
                scan_before_process=scan_before_process,
            )
            if result.status == "error":
                worker_state.last_error = result.error or result.message
            elif result.status in {"completed", "idle"}:
                worker_state.last_success = datetime.now().isoformat()
    finally:
        worker_state.state = "idle"
        worker_state.task = None


def _wake_processing_loop() -> None:
    worker_state.wake_requested = True
    if worker_state.task is None or worker_state.task.done():
        worker_state.task = asyncio.create_task(_processing_loop())


def _wake_processing_loop_threadsafe(*, scan_before_process: bool = False) -> None:
    """Request processing from watcher/scheduler callbacks that may run in threads."""
    worker_state.wake_requested = True
    if scan_before_process:
        worker_state.pending_scan_requested = True
        worker_state.pending_scan_cutoff = None

    loop = worker_state.loop
    if loop and loop.is_running():
        loop.call_soon_threadsafe(_wake_processing_loop)
        return

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("Worker wake requested before event loop was available")
        return
    _wake_processing_loop()


def _parse_cron_expression(cron_expression: str) -> dict[str, str]:
    parts = cron_expression.split()
    if len(parts) != 5:
        raise ValueError(f"Expected 5-field cron expression, got: {cron_expression}")
    minute, hour, day, month, day_of_week = parts
    return {
        "minute": minute,
        "hour": hour,
        "day": day,
        "month": month,
        "day_of_week": day_of_week,
    }


def _scheduled_scan_and_wake(wake_worker: Callable[[], None]) -> None:
    try:
        scan_and_insert()
        wake_worker()
    except Exception:
        logger.exception("Scheduled scan failed")


def configure_scheduler(
    settings: Settings,
    *,
    scheduler: Any,
    wake_worker: Callable[[], None],
) -> bool:
    if not settings.schedule_enabled:
        return False

    cron_kwargs = _parse_cron_expression(settings.schedule_cron or "0 3 * * *")
    scheduler.add_job(
        lambda: _scheduled_scan_and_wake(wake_worker),
        "cron",
        id="supernote-scheduled-processing",
        replace_existing=True,
        **cron_kwargs,
    )
    return True


def start_watcher_and_scheduler(settings: Settings) -> None:
    if settings.watch_enabled and worker_state.watcher is None:
        observer = build_note_observer(
            settings,
            wake_worker=lambda: _wake_processing_loop_threadsafe(scan_before_process=False),
        )
        if observer is not None:
            observer.start()
            worker_state.watcher = observer
            logger.info("Started Supernote watcher")

    if settings.schedule_enabled and worker_state.scheduler is None:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()
        if configure_scheduler(
            settings,
            scheduler=scheduler,
            wake_worker=lambda: _wake_processing_loop_threadsafe(scan_before_process=False),
        ):
            scheduler.start()
            worker_state.scheduler = scheduler
            logger.info("Started Supernote scheduler")


def stop_watcher_and_scheduler() -> None:
    if worker_state.watcher is not None:
        worker_state.watcher.stop()
        worker_state.watcher.join(timeout=5)
        worker_state.watcher = None

    if worker_state.scheduler is not None:
        worker_state.scheduler.shutdown(wait=False)
        worker_state.scheduler = None


@app.on_event("startup")
async def startup_runtime() -> None:
    settings = _init_runtime()
    reset_stale_processing_notes(settings.lock_stale_minutes)
    worker_state.loop = asyncio.get_running_loop()
    start_watcher_and_scheduler(settings)


@app.on_event("shutdown")
async def shutdown_runtime() -> None:
    stop_watcher_and_scheduler()
    worker_state.loop = None


@app.post("/process", status_code=202)
async def trigger_process() -> dict[str, Any]:
    """Scan recent notes and wake the in-process worker if work is pending."""
    settings = _init_runtime()

    if worker_state.state == "running":
        worker_state.pending_scan_requested = True
        worker_state.pending_scan_cutoff = _recent_cutoff()
        worker_state.wake_requested = True
        return {
            "status": "accepted",
            "message": "Processing is already active; wake-up coalesced",
        }

    if _lock_blocks_processing(settings):
        return {
            "status": "already_running",
            "message": "Processing is already running",
        }

    cutoff = _recent_cutoff()
    scanned = scan_and_insert(cutoff_date=cutoff)
    reset_stale_processing_notes(settings.lock_stale_minutes)
    pending = get_pending_notes()
    if not pending:
        return {
            "status": "idle",
            "message": "No files to process",
            "scanned": scanned,
        }

    _wake_processing_loop()
    return {
        "status": "accepted",
        "message": f"Processing {len(pending)} note(s) in background",
        "pending_count": len(pending),
        "scanned": scanned,
    }


@app.get("/status")
def get_status() -> dict[str, Any]:
    """Return queue counts and lightweight worker health details."""
    settings = _init_runtime()
    return {
        "counts": count_notes_by_status(),
        "worker": {
            "state": worker_state.state,
            "current_note": worker_state.current_note,
            "last_success": worker_state.last_success,
            "last_error": worker_state.last_error,
            "lock": get_processing_lock(),
        },
        "watcher": {
            "status": "running" if worker_state.watcher is not None else "stopped",
            "enabled": settings.watch_enabled,
        },
        "next_scheduled_run": (
            worker_state.scheduler.get_jobs()[0].next_run_time.isoformat()
            if worker_state.scheduler is not None
            and worker_state.scheduler.get_jobs()
            and worker_state.scheduler.get_jobs()[0].next_run_time is not None
            else None
        ),
        "ocr": {
            "provider": settings.ocr_provider,
            "reachable": None,
            "message": "not checked",
        },
    }


@app.get("/health")
def health() -> Any:
    """Report process and database health."""
    try:
        _init_runtime()
        count_notes_by_status()
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "unavailable",
                "error": str(exc),
            },
        )

    return {
        "status": "ok",
        "database": "ok",
        "worker_state": worker_state.state,
    }
