"""Minimal webhook server for triggering background processing."""
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from fastapi import FastAPI
from app.database import init_db, get_pending_notes, get_recent_activity
from app.services.scanner import scan_and_insert

app = FastAPI(title="Supernote Webhook")

LOOKBACK_DAYS = 7


@app.post("/process", status_code=202)
def trigger_process():
    """Scan for recent notes and process any pending ones."""
    init_db()
    cutoff = date.today() - timedelta(days=LOOKBACK_DAYS)
    scan_and_insert(cutoff_date=cutoff)
    pending = get_pending_notes()
    if not pending:
        return {"status": "idle", "message": "No files to process"}
    subprocess.Popen(
        [sys.executable, "-m", "app", "--process", "--cutoff", cutoff.isoformat()],
        start_new_session=True,
        cwd=str(Path(__file__).parent.parent),
    )
    return {
        "status": "accepted",
        "message": f"Processing {len(pending)} note(s) in background",
    }


@app.get("/status")
def get_status():
    """Return current queue counts from the database."""
    init_db()
    pending = get_pending_notes()
    activity = get_recent_activity(limit=5)
    return {
        "pending_count": len(pending),
        "recent_activity": activity,
    }


@app.get("/health")
def health():
    return {"status": "ok"}
