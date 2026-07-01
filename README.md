# Supernote Converter

A Python Streamlit application that converts handwritten Supernote `.note` files into searchable Markdown for Obsidian. It uses local llama-server vision OCR by default, keeps Ollama available as an optional local provider, and can fall back to OpenAI.

## Features

* **Scanning:** Detects `.note` files in a synchronized Supernote directory.
* **Conversion:** Converts Supernote pages to PNG images.
* **OCR:** Extracts text from images using llama-server by default, Ollama optionally, and OpenAI as fallback.
* **Review UI:** Streamlit review queue for checking, editing, and approving extracted text alongside the original image.
* **Export:** Writes Markdown files with Obsidian-friendly frontmatter.
* **Worker:** FastAPI worker owns background processing, locking, watcher, scheduler, health, and status endpoints.
* **Automation:** File watcher and scheduler can replace n8n after deployed verification confirms the new watcher/scheduler behavior in production.
* **Notifications:** Optional non-blocking Pushover notifications for start, completion, errors, and review-needed runs.

## Prerequisites

* Python 3.11.
* llama-server reachable with a multimodal vision model.
* Optional: Ollama reachable with a vision model such as `qwen3-vl:8b`.
* Optional: OpenAI API key for fallback OCR.

## Windows Development Setup

Open PowerShell in the project root.

### 1. Set Up A Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy the example file, then edit `.env` for your local paths and OCR services:

```powershell
copy .env.example .env
```

Important path settings:

* `SOURCE_PATH`: directory containing synced Supernote `.note` files.
* `OUTPUT_PATH`: Obsidian Journals output directory.
* `DATABASE_PATH`: SQLite database path, usually `data/supernote.db`.
* `PNG_CACHE_PATH`: PNG export cache path, usually `data/png_cache`.

OCR settings:

* `OCR_PROVIDER=llama_server` for the default local provider.
* `LLAMA_SERVER_URL` and `LLAMA_SERVER_MODEL` for llama-server.
* `OLLAMA_URL` and `OLLAMA_MODEL` if using Ollama instead.
* `OPENAI_API_KEY` for fallback OCR.

### 4. Run Locally

Run the worker and Streamlit in separate PowerShell terminals:

```powershell
uvicorn app.worker:app --host 127.0.0.1 --port 8000
```

```powershell
streamlit run app/Home.py
```

Open `http://localhost:8501`. The UI delegates processing to the worker at `http://127.0.0.1:8000`; if the worker is not running, the UI shows a worker-unavailable state instead of processing in the Streamlit session.

## CLI / Headless Mode

The CLI uses the same lock-aware processing path as the worker.

```powershell
python -m app --process
python -m app --process --cutoff 2026-01-01
python -m app --version
```

## Worker Endpoints

The worker listens on port `8000` inside the container. On the current Unraid deployment this is expected to be mapped as `8002 -> 8000` once the Unraid compose file is updated.

| Method | Local URL | Purpose |
| --- | --- | --- |
| `POST` | `http://127.0.0.1:8000/process` | Scan recent notes, wake the worker, and return `accepted`, `idle`, or `already_running`. |
| `GET` | `http://127.0.0.1:8000/status` | Return queue counts, worker state, current note, lock state, watcher status, next scheduled run, and OCR provider. |
| `GET` | `http://127.0.0.1:8000/health` | Return process/database health; unhealthy runtime state returns HTTP 503. |
| `GET` | `http://127.0.0.1:8000/activity?limit=20` | Return recent activity log entries (`limit` 1-500). |
| `GET` | `http://127.0.0.1:8000/queue/review` | Return notes awaiting review plus status counts. |
| `GET` | `http://127.0.0.1:8000/notes` | Return filtered, paginated note history (`status`, `search`, `limit`, `offset`). |
| `GET` | `http://127.0.0.1:8000/notes/{note_id}` | Return a note with its extractions; HTTP 404 if unknown. |

The read endpoints are unauthenticated. Keep the worker port on a trusted LAN/VPN only until auth is added.

`POST /process` returns immediately while processing continues in the background. Repeated wake-ups are coalesced and protected by the SQLite processing lock.

## Watcher, Scheduler, And Notifications

Watcher settings:

* `WATCH_ENABLED=true` enables recursive polling for `*.note` files.
* `WATCH_STABLE_SECONDS=60` requires a note file to stop changing before it is queued.
* `WATCH_POLL_SECONDS=15` controls the polling interval.

Scheduler settings:

* `SCHEDULE_ENABLED=false` disables the safety-net scheduler by default.
* `SCHEDULE_CRON=0 3 * * *` schedules a daily 3am scan and worker wake-up when enabled.

Watcher and scheduler settings are loaded when the worker starts. Restart the
worker/container after changing `WATCH_*` or `SCHEDULE_*` values in the Settings
page or environment.

Lock recovery:

* `LOCK_STALE_MINUTES=15` controls when an abandoned processing lock can be stolen and stale `processing` notes can be reset.

Pushover notification settings:

* `NOTIFY_ENABLED=false`
* `PUSHOVER_TOKEN=`
* `PUSHOVER_USER=`
* `NOTIFY_ON_START=true`
* `NOTIFY_ON_COMPLETE=true`
* `NOTIFY_ON_ERROR=true`
* `NOTIFY_ON_REVIEW=true`

Notification sends are non-blocking and non-fatal; a Pushover outage should not fail note processing.

## Docker

The container starts both processes through `start.sh`:

* `uvicorn app.worker:app --host 0.0.0.0 --port 8000`
* `streamlit run app/Home.py --server.address 0.0.0.0`

If either process exits, `start.sh` exits so Docker can restart the container. The Docker healthcheck checks both Streamlit (`8501/_stcore/health`) and the worker (`8000/health`).

For local Docker testing:

```powershell
docker-compose build
docker-compose up -d
```

## Unraid Deployment Caveat

The repo `docker-compose.yml` is not the compose file used by Unraid. Unraid uses:

```text
/boot/config/plugins/compose.manager/projects/supernote-converter/docker-compose.yml
```

After this image is published, update that Unraid compose file with the worker port, watcher/scheduler settings, and optional Pushover variables before treating the watcher/scheduler as a production replacement for n8n.

Current expected published image:

```text
ghcr.io/al-how/supernote-scribe:latest
```

Current expected Unraid port mapping:

```text
8086 -> 8501  Streamlit
8002 -> 8000  Worker
```

## Tests

`pytest.ini` supplies the standard options, including `--basetemp=pytest-temp`, so the normal command is:

```powershell
pytest
```

Equivalent explicit command:

```powershell
pytest --tb=short -q --basetemp=pytest-temp
```

## Project Structure

* `app/Home.py`: Streamlit dashboard entry point.
* `app/pages/`: Scan, Review, History, and Settings pages.
* `app/worker.py`: FastAPI worker for processing, status, health, watcher, scheduler, and lock-aware CLI path.
* `app/services/`: Scanner, exporter, OCR, processor, Markdown, watcher, notifications, and connectivity helpers.
* `app/database.py`: SQLite schema, settings, notes, activity log, and processing lock helpers.
* `data/`: Local database and PNG cache runtime storage.
