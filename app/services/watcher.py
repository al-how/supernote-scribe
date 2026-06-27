"""Polling file watcher for newly changed Supernote files."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.config import Settings
from app.services.scanner import scan_file_and_insert

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileSnapshot:
    size: int
    mtime: float


SnapshotFunc = Callable[[Path], FileSnapshot]
SleepFunc = Callable[[float], None]
ScanFileFunc = Callable[[Path], tuple[int, int, int]]
WakeWorkerFunc = Callable[[], None]


def file_snapshot(path: Path) -> FileSnapshot:
    stat = path.stat()
    return FileSnapshot(size=stat.st_size, mtime=stat.st_mtime)


class StableNoteMonitor:
    """Wait for a .note file to stop changing, then queue it for processing."""

    def __init__(
        self,
        *,
        stable_seconds: int,
        poll_seconds: int,
        scan_file: ScanFileFunc = scan_file_and_insert,
        wake_worker: WakeWorkerFunc,
        snapshot_func: SnapshotFunc = file_snapshot,
        sleep_func: SleepFunc = time.sleep,
        max_checks: int | None = None,
    ) -> None:
        self.stable_seconds = stable_seconds
        self.poll_seconds = poll_seconds
        self.scan_file = scan_file
        self.wake_worker = wake_worker
        self.snapshot_func = snapshot_func
        self.sleep_func = sleep_func
        self.max_checks = max_checks

    def process_when_stable(self, path: Path) -> bool:
        note_path = Path(path)
        if note_path.suffix != ".note" or not note_path.exists() or not note_path.is_file():
            return False

        try:
            previous = self.snapshot_func(note_path)
            stable_for = 0
            checks = 0

            while stable_for < self.stable_seconds:
                if self.max_checks is not None and checks >= self.max_checks:
                    return False
                checks += 1
                self.sleep_func(self.poll_seconds)
                current = self.snapshot_func(note_path)
                if current == previous:
                    stable_for += self.poll_seconds
                else:
                    stable_for = 0
                    previous = current

            scanned = self.scan_file(note_path)
            if scanned[0] or scanned[1]:
                self.wake_worker()
            return True
        except FileNotFoundError:
            return False
        except Exception:
            logger.exception("Watcher failed while handling %s", note_path)
            return False


def build_note_observer(
    settings: Settings,
    *,
    wake_worker: WakeWorkerFunc,
    observer_factory: Callable[[float], object] | None = None,
) -> object | None:
    """Build and schedule a recursive PollingObserver for .note files."""
    if not settings.watch_enabled:
        return None

    source_path = Path(settings.source_path)
    if not source_path.exists():
        logger.warning("Watcher source path does not exist: %s", source_path)
        return None

    if observer_factory is None:
        from watchdog.observers.polling import PollingObserver

        observer_factory = lambda timeout: PollingObserver(timeout=timeout)

    from watchdog.events import FileSystemEventHandler

    monitor = StableNoteMonitor(
        stable_seconds=settings.watch_stable_seconds,
        poll_seconds=settings.watch_poll_seconds,
        wake_worker=wake_worker,
    )

    class NoteEventHandler(FileSystemEventHandler):
        def on_created(self, event) -> None:  # type: ignore[no-untyped-def]
            self._handle(event)

        def on_modified(self, event) -> None:  # type: ignore[no-untyped-def]
            self._handle(event)

        def _handle(self, event) -> None:  # type: ignore[no-untyped-def]
            if getattr(event, "is_directory", False):
                return
            monitor.process_when_stable(Path(event.src_path))

    observer = observer_factory(settings.watch_poll_seconds)
    observer.schedule(NoteEventHandler(), str(source_path), recursive=True)
    return observer
