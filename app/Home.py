"""Main Streamlit application - Dashboard page."""

import streamlit as st
import pandas as pd
from app.database import init_db, count_notes_by_status, get_recent_activity
import app.styles as styles

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

# Fetch stats
stats = count_notes_by_status()
pending_count = stats.get("pending", 0)
review_count = stats.get("review", 0)
processed_count = stats.get("approved", 0) + stats.get("auto_approved", 0)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="Pending Notes", value=str(pending_count))

with col2:
    st.metric(label="In Review", value=str(review_count))

with col3:
    st.metric(label="Processed", value=str(processed_count))

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
    **Configuration:**
    - Source Path: `{config['source_path']}`
    - Output Path: `{config['output_path']}`
    - Ollama URL: `{config['ollama_url']}`
    - Ollama Model: `{config['ollama_model']}`
    - Auto-Approve Threshold: {config['auto_approve_threshold']} chars

    **Database:** SQLite (initialized)

    Navigate to **Settings** to modify configuration.
    """)
