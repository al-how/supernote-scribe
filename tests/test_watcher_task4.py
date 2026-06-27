from pathlib import Path


def test_stable_note_event_waits_until_file_stops_changing(tmp_path, monkeypatch):
    from app.services import watcher

    note_path = tmp_path / "changed.note"
    note_path.write_bytes(b"one")
    scanned = []
    wakes = []
    snapshots = iter(
        [
            watcher.FileSnapshot(size=3, mtime=10.0),
            watcher.FileSnapshot(size=4, mtime=11.0),
            watcher.FileSnapshot(size=4, mtime=11.0),
            watcher.FileSnapshot(size=4, mtime=11.0),
        ]
    )

    monitor = watcher.StableNoteMonitor(
        stable_seconds=2,
        poll_seconds=1,
        scan_file=lambda path: scanned.append(path) or (1, 0, 0),
        wake_worker=lambda: wakes.append("wake"),
        snapshot_func=lambda path: next(snapshots),
        sleep_func=lambda seconds: None,
    )

    assert monitor.process_when_stable(note_path) is True
    assert scanned == [note_path]
    assert wakes == ["wake"]


def test_stable_note_event_does_not_scan_while_still_changing(tmp_path):
    from app.services import watcher

    note_path = tmp_path / "changing.note"
    note_path.write_bytes(b"one")
    scanned = []
    wakes = []
    snapshots = iter(
        [
            watcher.FileSnapshot(size=3, mtime=10.0),
            watcher.FileSnapshot(size=4, mtime=11.0),
            watcher.FileSnapshot(size=5, mtime=12.0),
            watcher.FileSnapshot(size=6, mtime=13.0),
        ]
    )

    monitor = watcher.StableNoteMonitor(
        stable_seconds=2,
        poll_seconds=1,
        scan_file=lambda path: scanned.append(path) or (1, 0, 0),
        wake_worker=lambda: wakes.append("wake"),
        snapshot_func=lambda path: next(snapshots),
        sleep_func=lambda seconds: None,
        max_checks=3,
    )

    assert monitor.process_when_stable(note_path) is False
    assert scanned == []
    assert wakes == []


def test_watcher_ignores_non_note_files(tmp_path):
    from app.services import watcher

    text_path = tmp_path / "ignore.txt"
    text_path.write_text("ignore")
    scanned = []

    monitor = watcher.StableNoteMonitor(
        stable_seconds=1,
        poll_seconds=1,
        scan_file=lambda path: scanned.append(path) or (1, 0, 0),
        wake_worker=lambda: None,
    )

    assert monitor.process_when_stable(text_path) is False
    assert scanned == []


def test_watcher_uses_polling_observer_recursively(tmp_path, monkeypatch):
    from app.config import Settings
    from app.services import watcher

    scheduled = []

    class FakeObserver:
        def schedule(self, handler, path, recursive):
            scheduled.append((handler, Path(path), recursive))

    observer = watcher.build_note_observer(
        Settings(source_path=tmp_path, watch_stable_seconds=5, watch_poll_seconds=2),
        wake_worker=lambda: None,
        observer_factory=lambda timeout: FakeObserver(),
    )

    assert observer is not None
    assert scheduled[0][1] == tmp_path
    assert scheduled[0][2] is True
