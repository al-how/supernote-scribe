"""Minimal webhook server for triggering background processing."""
import subprocess
import sys
from pathlib import Path
from fastapi import FastAPI
from app.database import init_db, get_pending_notes, get_recent_activity

app = FastAPI(title="Supernote Webhook")

@app.post("/process", status_code=202)
def trigger_process():
    """Spawn headless processor as detached subprocess and return immediately."""
    subprocess.Popen(
        [sys.executable, "-m", "app", "--process"],
        start_new_session=True,
        cwd=str(Path(__file__).parent.parent),
    )
    return {"status": "accepted", "message": "Processing started in background"}

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
