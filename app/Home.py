"""Main Streamlit application - Dashboard page."""

import streamlit as st
from app.database import init_db

# Initialize database on app startup
init_db()

st.set_page_config(
    page_title="Supernote Converter",
    page_icon="📝",
    layout="wide"
)

st.title("📝 Supernote Converter")
st.markdown("Convert handwritten Supernote files to searchable markdown using AI vision OCR.")

# Status Cards
st.subheader("📊 Status Overview")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="Pending Notes", value="0")

with col2:
    st.metric(label="In Review", value="0")

with col3:
    st.metric(label="Processed", value="0")

# Quick Actions
st.divider()
st.subheader("⚡ Quick Actions")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🔍 Scan for New Notes", use_container_width=True):
        st.info("Navigate to **Scan** page to discover new .note files")

with col2:
    if st.button("✏️ Review Queue", use_container_width=True):
        st.info("Navigate to **Review** page to approve pending extractions")

with col3:
    if st.button("📜 View History", use_container_width=True):
        st.info("Navigate to **History** page to see all processed notes")

# Recent Activity
st.divider()
st.subheader("📋 Recent Activity")
st.info("No recent activity. Start by scanning for notes or configuring settings.")

# System Info
st.divider()
with st.expander("ℹ️ System Information"):
    from app.config import get_settings
    config = get_settings()

    st.markdown(f"""
    **Configuration:**
    - Source Path: `{config.source_path}`
    - Output Path: `{config.output_path}`
    - Ollama URL: `{config.ollama_url}`
    - Ollama Model: `{config.ollama_model}`
    - Auto-Approve Threshold: {config.auto_approve_threshold} chars

    **Database:** SQLite (initialized)

    Navigate to **Settings** to modify configuration.
    """)
