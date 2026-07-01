# Plan: Worker Read-Cluster API Endpoints

## Context

The FastAPI worker (`app/worker.py`) currently exposes only three endpoints:
`POST /process`, `GET /status`, `GET /health`. All the richer state — the review
queue, note history, per-note extractions, and the activity log — lives only in the
SQLite layer (`app/database.py`) and is reachable only through the Streamlit UI.

The user wants to begin expanding the worker API, starting with a **read cluster**:
low-risk `GET` endpoints that promote existing DB read functions over HTTP. This
unlocks a remote/automation-facing view of the pipeline (dashboards, n8n-style
workflows, mobile status checks) without touching the auth question that write/action
endpoints would force. The queued task "Add Supernote Scribe worker activity API
endpoint" is the first item in this cluster.

All new endpoints are thin wrappers over functions that already exist and are already
tested via the DB layer, so this is additive and low-risk.

## Scope

Add four read endpoints to `app/worker.py`. No new business logic, no DB schema
changes, no auth (deferred — worker is LAN-only today; noted as out of scope).

**Security caveat (even though auth is deferred):** these endpoints expose file paths,
raw + edited OCR text, and activity-log details with no authentication. That is
acceptable for read-only use on a trusted LAN, but **the worker port (8002 → 8000)
must not be exposed beyond a trusted LAN/VPN until auth exists.** This constraint is a
prerequisite for the later action-endpoint slice.

| Endpoint | Wraps (in `app/database.py`) | Returns |
|----------|------------------------------|---------|
| `GET /activity?limit=20` | `get_recent_activity(limit)` | recent activity log rows (details JSON already parsed) |
| `GET /queue/review` | `get_review_queue()` + `count_notes_by_status()` | notes awaiting review + status counts |
| `GET /notes` | `get_notes_history(...)` | filtered/paginated note history |
| `GET /notes/{note_id}` | `get_note_by_id()` + `get_extractions_for_note()` | note detail with its extractions; 404 if missing |

`GET /notes/{note_id}/text` (aggregated markdown via `get_aggregated_text()`) is
**deferred** to keep this first slice tight — add later if a consumer needs it.

## Design decisions (match existing conventions)

- **Plain dict returns**, same as `/status` and `/process` (`dict[str, Any]`). No
  Pydantic response models — keep it simple, consistent with the current file.
- **Call `_init_runtime()` first** in every handler, exactly like the existing
  endpoints, so DB path/init is guaranteed before any query.
- **Imports:** extend the existing `from app.database import (...)` block in
  `app/worker.py:18` with `get_recent_activity`, `get_review_queue`,
  `get_notes_history`, `get_note_by_id`, `get_extractions_for_note`.
- **`GET /notes` query params** (mirror the `get_notes_history` signature, minimal set):
  `status` (optional, repeatable → list), `search` (optional), `limit`, `offset`.
  Skip `source`/`date_from`/`date_to` for now (YAGNI — easy to add later since the DB
  function already supports them). The handler maps these to
  `get_notes_history(status_filter=status, search_term=search, limit=limit, offset=offset)`
  — note the param rename (`status` → `status_filter`, `search` → `search_term`).
- **Bounded numeric params** (applies to `/activity` and `/notes`): use FastAPI `Query`
  constraints so bad input can't misbehave or run away:
  - `/activity`: `limit: int = Query(20, ge=1, le=500)`
  - `/notes`: `limit: int = Query(100, ge=1, le=500)`, `offset: int = Query(0, ge=0)`
- **404 for missing note:** raise `fastapi.HTTPException(status_code=404)` in
  `GET /notes/{note_id}`. (Add `from fastapi import FastAPI, HTTPException, Query` to
  the existing import at `app/worker.py:14`.)
- **`GET /notes/{note_id}` shape:** `{"note": <row>, "extractions": [<rows>]}`.
  Intentional contract note: the extraction rows include `raw_text` and `edited_text`,
  i.e. full OCR content is exposed by this endpoint by design (useful for consumers;
  named here so it's a deliberate contract, not an accident).
- **`GET /queue/review` shape:** `{"counts": count_notes_by_status(), "notes": [...]}`.
  Deliberately using `notes` (not `review`) as the list key so list payloads are
  consistent across `/notes` and `/queue/review`; `counts` parallels `/status`.

## Files to modify

- `app/worker.py` — add the four handlers (after the existing `/health` at line 431)
  and extend the two import blocks. This is the only source file that changes.
- `app/__init__.py` — bump `__version__` from `0.4.0` → `0.5.0` (per CLAUDE.md:
  always bump version on commit).
- `CLAUDE.md` — add the four routes to the "Worker Endpoints" section (currently lists
  only `/process`, `/status`, `/health` at `CLAUDE.md:94`).
- `README.md` — add the four routes to its endpoint list (currently `/process`,
  `/status`, `/health` at `README.md:86`).

Docs are **in scope for this change**, updated in the same commit as the code.

## Tests

Add `tests/test_worker_read_endpoints.py` following the existing pattern in
`tests/test_worker_task2.py` (`TestClient(app)` + the `test_db` fixture from
`tests/conftest.py`, seeding via `insert_note` / `insert_extraction` / `log_activity`):

- `/activity` returns logged events; respects `limit`.
- `/queue/review` returns only `review`-status notes and includes counts.
- `/notes` returns history; `status` and `search` filters narrow results; `limit`/`offset` paginate.
- `/notes/{id}` returns note + extractions for an existing note.
- `/notes/{id}` returns **404** for a missing id.
- `/activity` calls `_init_runtime()` (monkeypatch it and assert invoked), mirroring
  the existing `/process` runtime-init test — covers the "every read handler inits
  runtime" requirement.
- Bounds are enforced: `/activity?limit=0` and `/notes?limit=0` return **422**.

## Verification

```powershell
# Unit tests
pytest tests/test_worker_read_endpoints.py -v
pytest   # full suite, confirm no regressions

# Manual smoke test against a running worker
uvicorn app.worker:app --host 127.0.0.1 --port 8000
# in a second terminal:
curl http://127.0.0.1:8000/activity?limit=5
curl http://127.0.0.1:8000/queue/review
curl "http://127.0.0.1:8000/notes?limit=5"
curl http://127.0.0.1:8000/notes/1
curl -i http://127.0.0.1:8000/notes/999999   # expect HTTP 404
```

## Out of scope (future slices)

- Auth / API key (needed before action endpoints or WAN exposure).
- `GET /notes/{id}/text` aggregated markdown.
- Action endpoints (approve / reject / reprocess) and outbound event webhooks.
