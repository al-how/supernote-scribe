# Reliability Worker Watcher Notifications Implementation Plan

**Goal:** Make Supernote Converter run unattended through a supervised worker, automatic watcher/scheduler triggers, Pushover notifications, and reliable operational status.

**Architecture:** Keep one deployed container with Streamlit plus a FastAPI worker. The worker owns all processing, locking, watcher, scheduler, webhook, and notification behavior; Streamlit becomes a thin client. Use the existing SQLite database as the concurrency and status source of truth.

**Tech Stack:** Python 3.11, Streamlit, FastAPI, SQLite, httpx, watchdog PollingObserver, APScheduler, pytest.

## Global Constraints

- Do not add user-facing conversion features.
- Do not remove Ollama or OpenAI fallback support.
- Keep `python -m app --process` working.
- Keep `.abort_processing` as the abort mechanism.
- Use PowerShell command syntax in repo docs where local commands are listed.
- Use `pytest --tb=short -q --basetemp=pytest-temp` as the local verification command.
- Update `app/__init__.py` version before committing.
- Write all implementation plans under `.Codex/plans/`.

## Task 1: Foundation - Settings, Test Tracking, Scanner Helper, DB Lock

**Files:**
- Modify: `.gitignore`
- Modify: `.env.example`
- Modify: `app/config.py`
- Modify: `app/settings_manager.py`
- Modify: `app/pages/4_Settings.py`
- Modify: `app/database.py`
- Modify: `app/services/scanner.py`
- Create/modify tests under `tests/`

**Requirements:**
- Reconcile `.gitignore` so real tests can be tracked; keep generated outputs ignored: `pytest-temp/`, `.pytest_cache/`, `.abort_processing`, DB files, caches.
- Add settings fields: `watch_enabled`, `watch_stable_seconds`, `watch_poll_seconds`, `notify_enabled`, `pushover_token`, `pushover_user`, `notify_on_start`, `notify_on_complete`, `notify_on_error`, `notify_on_review`, `lock_stale_minutes`, and existing `schedule_cron`.
- Ensure `SettingsManager.get_all()` includes every new field and preserves correct bool/int/path/string types.
- Add Settings page controls for watcher, scheduler cron, notifications, and lock stale minutes.
- Add migration for `processing_lock`.
- Add lock helpers with owner token and atomic SQLite write transaction:
  - `acquire_processing_lock(owner: str, stale_minutes: int) -> str` returning `"acquired"`, `"already_running"`, or `"stale_stolen"`.
  - `release_processing_lock(owner: str) -> bool`.
  - `heartbeat_processing_lock(owner: str) -> bool`.
  - `get_processing_lock() -> dict | None`.
  - `reset_stale_processing_notes(stale_minutes: int) -> int`.
- Add `scan_file_and_insert(file_path: Path) -> tuple[int, int, int]` for one `.note` path. It must insert new, update changed, skip unchanged, and ignore/reject non-note or missing paths without scanning the entire source tree.

**Tests to add/run first (RED before production code):**
- Settings manager round-trips new bool/int/string fields.
- Lock acquire/contended/stale-steal/release/heartbeat behavior.
- Stale processing note reset behavior.
- Single-file scan inserts, updates, skips unchanged, and ignores non-note paths.

**Verification:**
- Run focused tests for new settings, database, and scanner behavior.
- Run `pytest --tb=short -q --basetemp=pytest-temp`.

## Task 2: Worker API, Processing Lock Integration, CLI/Webhook Unification

**Files:**
- Create: `app/worker.py`
- Modify: `app/webhook.py` or replace its runtime usage with `app.worker`
- Modify: `app/services/processor.py`
- Modify: `app/__main__.py`
- Modify tests under `tests/`

**Requirements:**
- Add FastAPI worker with `/process`, `/status`, and `/health`.
- `/process` scans recent notes where appropriate, attempts lock-aware worker wake-up, and returns `accepted`, `idle`, or `already_running`.
- Worker has one processing loop that coalesces wake-ups and runs blocking processing via `asyncio.to_thread`.
- Processing loop acquires DB lock, resets stale processing notes on startup/stale steal, heartbeats per note, releases lock in `finally`, and honors `.abort_processing`.
- `process_pending_notes()` accepts optional heartbeat/current-note callbacks without owning the lock itself.
- CLI `python -m app --process` uses the same lock/recovery path and returns cleanly when already running.
- `/status` returns counts by state, worker state, current note if any, last success, last error, watcher status placeholder, next scheduled run placeholder, OCR provider, and OCR reachability if cheap/non-blocking.
- `/health` reflects worker process health and database accessibility.

**Tests to add/run first:**
- `/process` returns `already_running` when lock is held.
- `/process` returns `idle` when scan finds no pending notes.
- `/status` returns counts and worker state shape.
- CLI/process wrapper does not run processing when lock is held.
- Processor invokes heartbeat/current-note callbacks per note.

**Verification:**
- Run focused worker/processor tests.
- Run `pytest --tb=short -q --basetemp=pytest-temp`.

## Task 3: Streamlit Delegation, Dashboard Status, Supervision, Healthcheck

**Files:**
- Modify: `app/pages/1_Scan.py`
- Modify: `app/Home.py`
- Modify: `start.sh`
- Modify: `Dockerfile`
- Modify: `README.md` and/or `CLAUDE.md`
- Modify tests where practical

**Requirements:**
- Remove in-session `process_pending_notes()` execution from Scan page.
- Process button scans/queues as before, then POSTs to worker `/process` at localhost/default worker URL.
- Scan/Home pages show clear worker-unavailable state if worker cannot be reached.
- Home dashboard reads expanded `/status` and displays operational status without claiming readiness when worker is down.
- Keep abort button behavior by writing `.abort_processing`.
- `start.sh` starts both worker and Streamlit and exits the container if either process dies.
- Docker healthcheck validates both Streamlit (`8501/_stcore/health`) and worker (`8000/health`).
- Docs include local two-process run commands:
  - `uvicorn app.worker:app --host 127.0.0.1 --port 8000`
  - `streamlit run app/Home.py`

**Tests to add/run first:**
- HTTP helper handles worker accepted/already_running/unavailable responses.
- Status formatting/helper handles worker-unavailable state.
- If shell-script testing is practical, test the healthcheck command shape; otherwise review manually.

**Verification:**
- Run focused UI helper tests.
- Run `pytest --tb=short -q --basetemp=pytest-temp`.

## Task 4: Watcher, Scheduler, Notifications

**Files:**
- Create: `app/services/watcher.py`
- Create: `app/services/notifications.py`
- Modify: `app/worker.py`
- Modify: `app/services/processor.py`
- Modify: `requirements.txt`
- Modify: `.env.example`
- Modify tests under `tests/`

**Requirements:**
- Add `watchdog` and `apscheduler`.
- Watcher uses `PollingObserver`, watches configured source path recursively for `*.note`, and debounces until size/mtime stable for `WATCH_STABLE_SECONDS` using poll interval `WATCH_POLL_SECONDS`.
- Stable watcher event calls `scan_file_and_insert(path)` and wakes the worker.
- Scheduler uses `schedule_enabled` and `schedule_cron`, defaults to 3am, scans source directory, and wakes the worker as a safety net.
- Notifications use Pushover with `httpx`, respect enable/per-event toggles, and never block or fail processing.
- Send start, complete, error, and review-needed notifications. Review-needed may be folded into completion with bumped priority when review count > 0.

**Tests to add/run first:**
- Watcher stable vs still-changing debounce logic.
- Watcher ignores non-note files.
- Notification payload/toggle behavior with mocked HTTP.
- Notification HTTP errors are logged/non-fatal.
- Scheduler job registration respects enabled/disabled setting.

**Verification:**
- Run focused watcher/notification/scheduler tests.
- Run `pytest --tb=short -q --basetemp=pytest-temp`.

## Task 5: CI, Docs, Version, Final Verification

**Files:**
- Modify: `.github/workflows/docker-publish.yml`
- Modify: `pytest.ini`
- Modify: `.gitignore` if not completed in Task 1
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `app/__init__.py`
- Modify: `docs/reliability-worker-watcher-notifications-plan.md` if implementation changed design details

**Requirements:**
- Add `pytest.ini` with the repo-standard test options, including `--basetemp=pytest-temp`.
- Add CI test job before Docker publish; Docker publish depends on tests.
- Document local dev, Docker behavior, worker endpoints, Pushover env vars, watcher/scheduler settings, and the Unraid deployment caveat that repo `docker-compose.yml` is not the Unraid compose file.
- Update version in `app/__init__.py`.
- Ensure docs do not claim n8n is retired until watcher/scheduler behavior has been verified.

**Verification:**
- Run `pytest --tb=short -q --basetemp=pytest-temp`.
- Run `python -m app --version`.
- Run any import smoke tests needed for `app.worker`.
- Report any verification that could not be completed locally.
