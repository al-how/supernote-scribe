# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## IMPORTANT

You are a coding agent assisting a non-coder. Resist the urge to over-engineer. DO NOT add features without discussing with the user.

Always write plans to this project directory, for example `C:\Users\alexn\Documents\Projects\supernote-converter\.claude\plans\[session_name].md`.

ALWAYS update the version number when committing changes.

You are operating in a PowerShell environment, so follow PowerShell conventions, for example semicolons instead of `&&` in CLI commands.

## Project Overview

Supernote Converter is a Python Streamlit web application that converts handwritten Supernote `.note` files into searchable Markdown for Obsidian. It uses local llama-server vision OCR as the default extraction method, keeps Ollama available as an optional local provider, and uses OpenAI gpt-4o as fallback.

## Status

* **Current State:** Fully functional and deployed.
* **Deployment:** Running on Unraid via Docker Compose.
* **Automation:** Worker-owned watcher and scheduler can replace n8n after deployed verification confirms production behavior.

## Tech Stack

* **Runtime:** Python 3.11
* **UI:** Streamlit multi-page app
* **Worker:** FastAPI on port 8000
* **Database:** SQLite local state, no external database
* **PNG Export:** supernotelib
* **OCR:** llama-server OpenAI-compatible API default, Ollama optional local provider, OpenAI fallback
* **HTTP Client:** httpx
* **Config:** Pydantic and pydantic-settings
* **Watcher/Scheduler:** watchdog PollingObserver and APScheduler
* **Deployment:** Docker on Unraid

## Commands

```powershell
# Install dependencies
pip install -r requirements.txt

# Run local worker
uvicorn app.worker:app --host 127.0.0.1 --port 8000

# Run Streamlit web UI in a second terminal
streamlit run app/Home.py

# Run headless processor
python -m app --process
python -m app --process --cutoff 2026-01-01

# Tests
pytest

# Docker
docker-compose build
docker-compose up -d
docker exec supernote-converter python -m app --process
```

## Architecture

```text
app/
|-- Home.py             # Streamlit main dashboard
|-- __main__.py         # CLI entry point (--process flag)
|-- config.py           # Pydantic settings from .env
|-- database.py         # SQLite schema, operations, and processing lock
|-- settings_manager.py # Dynamic settings management
|-- styles.py           # Custom CSS and UI styling
|-- worker.py           # FastAPI worker, processing loop, watcher, scheduler, endpoints
|-- pages/              # Streamlit multi-page UI
|   |-- 1_Scan.py       # Scan page delegates processing to worker
|   |-- 2_Review.py     # Review queue (PNG + text side-by-side)
|   |-- 3_History.py    # Processed notes history
|   `-- 4_Settings.py   # Configuration
`-- services/           # Business logic
    |-- scanner.py      # File discovery and filtering
    |-- exporter.py     # supernotelib PNG export
    |-- ocr.py          # llama-server, Ollama, and OpenAI vision OCR
    |-- processor.py    # Pipeline orchestration
    |-- markdown.py     # Frontmatter builder and output routing
    |-- watcher.py      # Polling file watcher and debounce
    |-- notifications.py # Non-fatal Pushover notifications
    `-- connection_tester.py # Service connectivity checks
```

**Data Flow:** Scan -> Export to PNG -> Vision OCR -> Review if needed -> Save to Journals.

The FastAPI worker owns background processing, locking, watcher, scheduler, and webhook behavior. Streamlit should not run long processing in-session; it asks the worker to process instead.

## Worker Endpoints

* `POST /process` scans recent notes and wakes processing; returns `accepted`, `idle`, or `already_running`.
* `GET /status` returns queue counts, worker state, current note, lock state, watcher status, next scheduled run, and OCR provider.
* `GET /health` checks process/database health and returns HTTP 503 for unhealthy runtime state.

Read endpoints (unauthenticated; keep the worker port on a trusted LAN/VPN only):

* `GET /activity?limit=20` returns recent activity log entries (limit 1-500).
* `GET /queue/review` returns notes awaiting review plus status counts.
* `GET /notes` returns filtered, paginated note history (`status`, `search`, `limit`, `offset`).
* `GET /notes/{note_id}` returns a note with its extractions; HTTP 404 if unknown.

## Database API (`app/database.py`)

Fully implemented SQLite layer with thread-safe connections for Streamlit and worker use.

```python
from app.database import init_db, get_pending_notes, mark_note_approved

# Initialize on startup
init_db()

# Key functions:
# Notes: insert_note, upsert_note, get_note_by_id, get_pending_notes, get_review_queue
# Status: mark_note_processing, mark_note_for_review, mark_note_approved, mark_note_error
# Reprocessing: reset_note_for_reprocessing (clears extractions, resets to pending)
# Extractions: insert_extraction, get_extractions_for_note, get_aggregated_text
# Settings: get_setting, set_setting
# Activity: log_activity, get_recent_activity
# Utilities: determine_source_folder, determine_output_folder
# Locking: acquire_processing_lock, heartbeat_processing_lock, release_processing_lock
```

**Tables:** `notes`, `extractions`, `settings`, `activity_log`, `schema_version`, `processing_lock`.

## Key Patterns

* **OCR Strategy:** All notes go through vision OCR. Default local provider is llama-server; Ollama remains selectable. Auto-approve if at least 200 characters.
* **Processing Lock:** Worker and CLI share the same SQLite-backed lock. Duplicate starts return `already_running`; stale locks can be recovered after `LOCK_STALE_MINUTES`.
* **Watcher:** `watchdog` PollingObserver recursively watches `*.note`, waits for size/mtime stability, then scans the single file and wakes the worker.
* **Scheduler:** APScheduler uses `SCHEDULE_ENABLED` and `SCHEDULE_CRON` as a safety-net scan/wake path.
* **Watcher/Scheduler Settings:** Running workers read watcher and scheduler settings at startup. Restart the worker/container after changing those values in Settings or environment.
* **Notifications:** Pushover sends are optional, non-blocking, and non-fatal.
* **Output Routing:** Path-based routing to Journals folders:
  * `/WORK/` -> `Journals/Work/`
  * `/Daily Journal/` -> `Journals/Daily/`
  * Other -> `Journals/Other/`
* **Line Break Processing:** Join lines not ending with `.!?:;`, preserve paragraphs and list items, keep short capitalized lines as headers.

## Deployment Details

* **Image:** `ghcr.io/al-how/supernote-scribe:latest` built via GitHub Actions.
* **Compose on Unraid:** `/boot/config/plugins/compose.manager/projects/supernote-converter/docker-compose.yml`.
* **DB on Unraid:** `/mnt/user/appdata/supernote-converter/supernote.db`.
* **Ports:** `8086 -> 8501` for Streamlit, `8002 -> 8000` for worker.
* The local `docker-compose.yml` in the repo is NOT what Unraid uses. Unraid has its own copy at the path above.

Redeploy on Unraid:

```powershell
ssh root@192.168.1.138
docker pull ghcr.io/al-how/supernote-scribe:latest
docker stop supernote-scribe
docker rm supernote-scribe
cd /boot/config/plugins/compose.manager/projects/supernote-converter
docker compose up -d
```

## Environment Variables

Required in `.env` when fallback OCR is needed:

* `OPENAI_API_KEY` - OpenAI API key for fallback OCR.

Set via docker-compose or shell:

* `SOURCE_PATH` - Path to Supernote sync directory.
* `OUTPUT_PATH` - Path to Obsidian Journals output.
* `OCR_PROVIDER` - Local OCR provider, `llama_server` default or `ollama`.
* `LLAMA_SERVER_URL` - llama-server URL, default `http://192.168.1.138:8080`.
* `LLAMA_SERVER_MODEL` - llama-server model name, default `llama-server`.
* `OLLAMA_URL` - Ollama server URL, default `http://192.168.1.138:11434`.
* `OLLAMA_MODEL` - Ollama model, default `qwen3-vl:8b`.
* `WATCH_ENABLED`, `WATCH_STABLE_SECONDS`, `WATCH_POLL_SECONDS`.
* `SCHEDULE_ENABLED`, `SCHEDULE_CRON`.
* `LOCK_STALE_MINUTES`.
* `NOTIFY_ENABLED`, `PUSHOVER_TOKEN`, `PUSHOVER_USER`.
* `NOTIFY_ON_START`, `NOTIFY_ON_COMPLETE`, `NOTIFY_ON_ERROR`, `NOTIFY_ON_REVIEW`.
