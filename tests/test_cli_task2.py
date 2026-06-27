from app.database import acquire_processing_lock


def test_cli_process_scans_without_cutoff(test_db, monkeypatch):
    from app import worker

    scan_calls = []

    monkeypatch.setattr(worker, "init_app", lambda: None)
    monkeypatch.setattr(
        worker,
        "scan_and_insert",
        lambda cutoff_date=None: scan_calls.append(cutoff_date) or (1, 0, 0),
    )
    monkeypatch.setattr(worker, "get_pending_notes", lambda: [])

    result = worker.run_cli_process(cutoff_date=None)

    assert result.status == "idle"
    assert result.scanned == (1, 0, 0)
    assert scan_calls == [None]


def test_cli_process_returns_cleanly_when_lock_is_held(test_db, monkeypatch, capsys):
    from app import __main__

    acquire_processing_lock("existing-worker", stale_minutes=15)
    monkeypatch.setattr(
        "app.worker.process_batch_with_lock",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
    )
    monkeypatch.setattr(__main__, "scan_and_insert", lambda cutoff_date=None: (0, 0, 0))
    monkeypatch.setattr("sys.argv", ["python -m app", "--process"])

    exit_code = __main__.main()

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "already running" in output.lower()
