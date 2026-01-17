"""Scan & Process page."""

import streamlit as st
import time
from datetime import date, timedelta
from app.services.scanner import scan_and_insert
from app.services.processor import process_pending_notes
from app.database import get_pending_notes, init_db

# Initialize DB
init_db()

st.set_page_config(page_title="Scan & Process", page_icon="🔍")

st.title("🔍 Scan & Process")
st.markdown("Discover new notes and process them with AI vision.")

# ============================================================================
# Scan Configuration
# ============================================================================
st.subheader("1. Scan for Notes")

col1, col2 = st.columns([2, 1])

with col1:
    # Default to 7 days ago to avoid scanning ancient history by default
    default_date = date.today() - timedelta(days=7)
    cutoff_date = st.date_input(
        "Cutoff Date",
        value=default_date,
        help="Only scan notes modified on or after this date"
    )

with col2:
    st.write("") # Spacer
    st.write("") # Spacer
    scan_btn = st.button("🔎 Scan Now", type="primary", use_container_width=True)

if scan_btn:
    with st.spinner("Scanning directory..."):
        # Convert date to datetime.date (streamlit returns date)
        new, updated, skipped = scan_and_insert(cutoff_date=cutoff_date)
        
        if new > 0 or updated > 0:
            st.success(f"Scan complete: {new} new, {updated} updated, {skipped} skipped.")
        else:
            st.info(f"No new notes found. ({skipped} skipped)")

# ============================================================================
# Process Configuration
# ============================================================================
st.divider()
st.subheader("2. Process Pending Notes")

# Check pending count
pending_notes = get_pending_notes()
pending_count = len(pending_notes)

if pending_count == 0:
    st.info("✅ No pending notes to process.")
else:
    st.warning(f"⚠️ **{pending_count}** notes are waiting to be processed.")
    
    with st.expander("View Pending List"):
        for note in pending_notes:
            st.text(f"- {note['file_name']} ({note['source_folder']})")

    if st.button(f"🚀 Process {pending_count} Notes", type="primary"):
        # Progress container
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_container = st.container()
        
        def progress_callback(stage: str, current: int, total: int, note_name: str):
            """Update UI progress."""
            if stage == "processing":
                percent = int((current / total) * 100)
                progress_bar.progress(percent)
                status_text.markdown(f"**Processing {current}/{total}:** `{note_name}`")
            elif stage == "complete":
                progress_bar.progress(100)
                status_text.success("Processing complete!")

        # Run processing
        with st.status("Processing pipeline running...", expanded=True) as status:
            result = process_pending_notes(progress_callback=progress_callback)
            
            status.write("---")
            status.write(f"**Processed:** {result.processed}")
            status.write(f"**Auto-approved:** {result.auto_approved}")
            status.write(f"**Queued for Review:** {result.review_queued}")
            
            if result.errors > 0:
                status.error(f"**Errors:** {result.errors}")
                for note_id, msg in result.error_details:
                    status.write(f"- Note ID {note_id}: {msg}")
            else:
                status.write("**Errors:** 0")
                
            status.update(label="Processing Complete", state="complete")

        st.success("Batch processing finished!")
        if result.review_queued > 0:
            st.info(f"👉 {result.review_queued} notes queued for review. Go to **Review** page.")
        
        # Rerun to update pending count
        time.sleep(2)
        st.rerun()
