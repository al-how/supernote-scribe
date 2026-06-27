# Supernote Converter - Reliability, Worker, Watcher & Notifications

**Date:** 2026-06-27
**Status:** Design approved; review gaps incorporated before implementation
**Related task:** `Personal_Vault/01-Projects/Tasks/Improve Supernote Converter reliability and operations.md`
**Related notes:** `docs/repo-improvements.md`
**Implementation handoff:** keep the executable task plan under `.Codex/plans/` per `AGENTS.md`; on Windows the directory may appear as `.codex`, but keep a single plan directory rather than duplicate case variants. This docs file remains the design record.

## Objective

Make the deployed Supernote Converter trustworthy to operate unattended. Specifically:

1. Jobs run reliably **without a browser open** to drive/monitor them.
2. A built-in **file watcher** triggers processing automatically and can replace n8n after deployed verification confirms watcher/scheduler behavior in production.
3. **Pushover notifications** to iPhone on job start, completion, errors, and review-needed.
4. Fold in the reliability fixes from the task file (webhook concurrency guard, richer status/health, CI test gate, reliable test command).

No new user-facing *conversion* features - this is reliability and operations work.

## Core Architectural Decision: Approach A - A Single Supervised Worker

The container runs **two processes**, supervised so that if *either* dies the container exits and Docker restarts it. This fixes the current silent-failure mode where a dead webhook can hide behind a live Streamlit process.

- **Worker** (`uvicorn app.worker:app`) owns *all* background work: file watcher, scheduler, note processing, and the webhook endpoints. There is exactly **one** processing path.
- **Streamlit UI** becomes *thin*: it scans, lets you select notes, displays live status, and asks the worker to do the work via a localhost call. It never processes notes itself.

```text
  cloud-sync .note file
          |
          v
  WORKER (uvicorn app.worker:app)
    - file watcher (polling + debounce)
    - scheduler (nightly safety-net)
    - webhook /process /status /health
    - one processing loop + lock
          |
          +--> OCR --> Journals/
          +--> Pushover

  Streamlit UI and iOS Shortcut both POST to the worker.
```

## Decisions Made

| Area | Decision | Notes / rationale |
|------|----------|-------------------|
| Architecture | Single supervised worker (Approach A) | One processing path; browser-independence is structural, not bolted on. |
| Process supervision | Small wrapper script that exits the container if either process dies; `restart: unless-stopped` recovers it. | Lighter than adding `supervisord` for this deployment. |
| Streamlit Process button | **Remove in-session processing.** Button now scans + asks the worker to run, then shows "job started - watch status / you will be notified." | In-session `process_pending_notes()` in `1_Scan.py` is the root brittleness. |
| Concurrency guard | DB-backed `processing_lock` with one row: locked, owner, locked_at, heartbeat. Acquire with an explicit SQLite write transaction (`BEGIN IMMEDIATE` or equivalent conditional update/insert) and an owner token; stale lock (>15 min, no heartbeat) is auto-stolen; lock is cleared in `finally`. | Duplicate `/process` returns `already_running`. Lock steal/startup recovery must repair abandoned `processing` notes. |
| Job queue | **No new queue table.** Pending notes already are the queue; the worker loop coalesces multiple wake-ups into one run. | YAGNI. |
| File watcher | `watchdog` **PollingObserver** watching `*.note`, with a ~60s debounce before queuing. Add `scan_file_and_insert(path)` or explicitly debounce to one directory scan. | Unraid FUSE share and cloud-sync writes make inotify unreliable. |
| Scheduler | APScheduler using existing `schedule_cron` / `schedule_enabled` settings; nightly sweep (default 3am) scans + wakes worker. `schedule_cron` must round-trip through DB-backed settings. | Safety-net, not primary trigger. |
| Notifications | Pushover, via `app/services/notifications.py`. Fully non-fatal. | Reliable iOS push and simple HTTP. |
| Notify events | **Start + Complete + Error + Review-needed.** Review-needed folded into completion with bumped priority when >0. | Per-event toggles exposed in settings. |
| Status/health | `/status` expands to counts-by-state, worker state, current note, last success, last error, watcher status, next run, OCR provider + reachability. `/health` checks both processes; Docker healthcheck pings both 8501 and 8000. | Answers "is it working / what happened last" at a glance. |
| Ops hardening | CI `pytest` job gating Docker publish; `pytest.ini` with `--basetemp=pytest-temp`; `.gitignore` reconciled. | From `docs/repo-improvements.md`. |
| CLI | Keep `python -m app --process` working and acquiring the same lock. | Manual headless runs stay available and safe. |
| Abort | Keep `.abort_processing`; worker honors it. | Reuses what works across processes. |
| Local development | Document how to run both services locally; UI shows worker-unavailable state if only Streamlit is running. | Avoids confusing local tests. |

## Components

- **`app/worker.py`** *(new)* - FastAPI worker, lifespan startup, scheduler/watcher startup, processing loop, status/health endpoints, stale recovery.
- **`app/services/watcher.py`** *(new)* - PollingObserver + debounce, calls single-file scan helper and wakes worker.
- **`app/services/notifications.py`** *(new)* - Pushover HTTP with non-fatal failures and event toggles.
- **`app/database.py`** *(changed)* - lock table, lock helpers, stale processing recovery, migration.
- **`app/services/scanner.py`** *(changed)* - `scan_file_and_insert(path)`.
- **`app/services/processor.py`** *(changed)* - heartbeat and notification callbacks in batch processing; no lock ownership inside single-note processing.
- **`app/pages/1_Scan.py`** *(changed)* - delegate to worker.
- **`app/Home.py`** *(changed)* - worker-backed status dashboard and degraded state.
- **`app/pages/4_Settings.py`**, **`app/config.py`**, **`app/settings_manager.py`**, **`.env.example`** *(changed)* - new settings and `schedule_cron` round-trip.
- **`start.sh`**, **`Dockerfile`**, **`requirements.txt`**, **`pytest.ini`**, **`.gitignore`**, **`.github/workflows/docker-publish.yml`**, **`CLAUDE.md`**, **`.Codex/plans/reliability-worker-watcher-notifications-plan.md`** *(changed / created)* - runtime and ops hardening.

## New Configuration / Environment Variables

Implemented defaults keep unattended triggers/notifications opt-in until the
Unraid deployment is verified:

```env
WATCH_ENABLED=true
WATCH_STABLE_SECONDS=60
WATCH_POLL_SECONDS=15
SCHEDULE_ENABLED=false
SCHEDULE_CRON=0 3 * * *
NOTIFY_ENABLED=false
PUSHOVER_TOKEN=...
PUSHOVER_USER=...
NOTIFY_ON_START=true
NOTIFY_ON_COMPLETE=true
NOTIFY_ON_ERROR=true
NOTIFY_ON_REVIEW=true
LOCK_STALE_MINUTES=15
```

These fields must be present in all relevant configuration surfaces: `app/config.py`, `app/settings_manager.py`, `app/pages/4_Settings.py`, `.env.example`, and deployment docs.

## Implementation Guardrails

- **Atomic lock acquire:** implement acquire/release in `app/database.py` with an owner token and one SQLite write transaction. The acquire path must return `acquired`, `already_running`, or `stale_stolen`.
- **Stale note recovery:** when a stale lock is stolen, and on worker startup, recover notes left in `processing` longer than `LOCK_STALE_MINUTES`. Reset to `pending` unless terminal output proves completion.
- **Watcher scan shape:** add `scan_file_and_insert(path)`. Full directory scans stay in `scan_and_insert()`.
- **Local run shape:** document local dev as `uvicorn app.worker:app --host 127.0.0.1 --port 8000` plus `streamlit run app/Home.py`.
- **Plan location:** maintain task-by-task implementation plan in `.Codex/plans/`.

## Build Order

0. Implementation handoff in `.Codex/plans/`.
1. Worker + browser independence.
2. File watcher.
3. Notifications.
4. Scheduler safety-net + ops hardening.
