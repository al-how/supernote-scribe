"""Main Streamlit application - Dashboard page."""

import streamlit as st
import pandas as pd
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import init_db, count_notes_by_status, get_recent_activity
from app.ui_worker import DEFAULT_WORKER_URL, fetch_worker_status, format_worker_status
import app.styles as styles
from app import __version__

# Initialize database on app startup
init_db()

st.set_page_config(
    page_title="Supernote Converter",
    page_icon="📝",
    layout="wide"
)
styles.load_css()

st.title("📝 Supernote Converter")
st.markdown("Convert handwritten Supernote files to searchable markdown using AI vision OCR.")

# Status Cards
st.subheader("📊 Status Overview")

worker_status = format_worker_status(fetch_worker_status())
if worker_status["available"]:
    st.success(f"{worker_status['label']}: {worker_status['summary']}")
else:
    st.error(f"{worker_status['label']}: {worker_status['summary']}")
    st.caption(f"Worker URL: `{DEFAULT_WORKER_URL}`")

fallback_stats = count_notes_by_status()
pending_count = worker_status["pending_count"] if worker_status["available"] else fallback_stats.get("pending", 0)
review_count = worker_status["review_count"] if worker_status["available"] else fallback_stats.get("review", 0)
processed_count = (
    worker_status["processed_count"]
    if worker_status["available"]
    else fallback_stats.get("approved", 0) + fallback_stats.get("auto_approved", 0)
)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="Pending Notes", value=str(pending_count))

with col2:
    st.metric(label="In Review", value=str(review_count))

with col3:
    st.metric(label="Processed", value=str(processed_count))

st.caption("Queue counts come from the worker when reachable; local database counts are shown when it is down.")

with st.expander("Worker Details", expanded=not worker_status["available"]):
    if worker_status["available"]:
        st.markdown(f"""
        - Current Note: `{worker_status['current_note'] or 'None'}`
        - Last Success: `{worker_status['last_success'] or 'None'}`
        - Last Error: `{worker_status['last_error'] or 'None'}`
        - Watcher Status: `{worker_status['watcher_status'] or 'None'}`
        - Next Scheduled Run: `{worker_status['next_scheduled_run'] or 'None'}`
        - OCR Provider: `{worker_status['ocr_provider'] or 'unknown'}`
        - OCR Check: `{worker_status['ocr_message'] or 'None'}`
        """)
    else:
        st.warning("The Streamlit UI is running, but the worker API is not reachable. Start the worker before processing notes.")

# Quick Actions
st.divider()
st.subheader("⚡ Quick Actions")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🔍 Scan for New Notes", use_container_width=True):
        st.switch_page("pages/1_Scan.py")

with col2:
    if st.button("✏️ Review Queue", use_container_width=True):
        st.switch_page("pages/2_Review.py")

with col3:
    if st.button("📜 View History", use_container_width=True):
        st.switch_page("pages/3_History.py")

# Recent Activity
st.divider()
st.subheader("📋 Recent Activity")

recent_logs = get_recent_activity(limit=5)

if not recent_logs:
    st.info("No recent activity. Start by scanning for notes or configuring settings.")
else:
    for log in recent_logs:
        with st.container():
            col_icon, col_time, col_msg = st.columns([0.5, 2, 8])
            
            # Icon based on event type
            icon = "ℹ️"
            if "scan" in log["event_type"].lower():
                icon = "🔍"
            elif "process" in log["event_type"].lower():
                icon = "⚙️"
            elif "approve" in log["event_type"].lower():
                icon = "✅"
            elif "error" in log["event_type"].lower():
                icon = "❌"
            
            col_icon.write(icon)
            col_time.caption(log["created_at"])
            col_msg.markdown(f"**{log['message']}**")

# System Info
st.divider()
with st.expander("ℹ️ System Information"):
    from app.settings_manager import SettingsManager
    
    # Get effective settings (DB overrides + defaults)
    manager = SettingsManager()
    config = manager.get_all()

    st.markdown(f"""
    **System:**
    - Version: `{__version__}`

    **Configuration:**
    - Source Path: `{config['source_path']}`
    - Output Path: `{config['output_path']}`
    - OCR Provider: `{config['ocr_provider']}`
    - llama-server URL: `{config['llama_server_url']}`
    - llama-server Model: `{config['llama_server_model']}`
    - Ollama URL: `{config['ollama_url']}`
    - Ollama Model: `{config['ollama_model']}`
    - Auto-Approve Threshold: {config['auto_approve_threshold']} chars

    **Database:** SQLite (initialized)

    Navigate to **Settings** to modify configuration.
    """)
