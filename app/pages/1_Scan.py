"""Scan & Process page."""

import streamlit as st
import time
from datetime import date, timedelta, datetime
from pathlib import Path
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.scanner import scan_source_directory
from app.services.processor import process_pending_notes
from app.database import get_pending_notes, init_db, upsert_note, get_note_by_path
import app.styles as styles

# Abort flag file (used to signal abort across Streamlit reruns)
ABORT_FLAG_FILE = Path(__file__).parent.parent.parent / ".abort_processing"

def set_abort_flag():
    """Set the abort flag by creating a file."""
    ABORT_FLAG_FILE.touch()

def clear_abort_flag():
    """Clear the abort flag by removing the file."""
    if ABORT_FLAG_FILE.exists():
        ABORT_FLAG_FILE.unlink()

def check_abort_flag() -> bool:
    """Check if abort was requested."""
    return ABORT_FLAG_FILE.exists()

# Initialize session state for logs
if "processing_logs" not in st.session_state:
    st.session_state.processing_logs = []

# Initialize session state for discovered notes selection
if "discovered_notes" not in st.session_state:
    st.session_state.discovered_notes = []

# Initialize DB
init_db()

st.set_page_config(page_title="Scan & Process", page_icon="🔍")
styles.load_css()

st.title("🔍 Scan & Process")
st.markdown("Discover new notes and process them with AI vision.")

# ============================================================================
# Scan Configuration
# ============================================================================
st.subheader("1. Scan for Notes")

# Initialize session state for cutoff date if not present
if "cutoff_date" not in st.session_state:
    # Default to 7 days ago
    st.session_state.cutoff_date = date.today() - timedelta(days=7)

col1, col2 = st.columns([2, 1])

with col1:
    cutoff_date = st.date_input(
        "Cutoff Date",
        value=st.session_state.cutoff_date,
        help="Only scan notes modified on or after this date"
    )
    # Update session state when value changes
    st.session_state.cutoff_date = cutoff_date

with col2:
    st.write("") # Spacer
    st.write("") # Spacer
    scan_btn = st.button("🔎 Scan Now", type="primary", use_container_width=True)

# Show current source path for clarity
from app.settings_manager import SettingsManager
current_source = SettingsManager().get("source_path")
st.caption(f"Scanning directory: `{current_source}`")

if scan_btn:
    with st.spinner(f"Scanning {current_source}..."):
        # Discover files without inserting into database
        discovered = scan_source_directory(cutoff_date=cutoff_date)

        # Add selection state and check if already in database
        for note in discovered:
            existing = get_note_by_path(note["file_path"])
            note["selected"] = True  # Default all selected
            note["status"] = "new" if existing is None else "exists"

        st.session_state.discovered_notes = discovered

        if discovered:
            st.success(f"Found {len(discovered)} notes. Select which ones to process below.")
        else:
            st.info("No notes found matching the cutoff date.")

# ============================================================================
# File Selection (shown after scan)
# ============================================================================
if st.session_state.discovered_notes:
    st.divider()
    st.subheader("2. Select Notes to Process")

    # Select All / Deselect All buttons
    col_all, col_none, col_clear = st.columns([1, 1, 1])
    with col_all:
        if st.button("Select All", use_container_width=True):
            for note in st.session_state.discovered_notes:
                note["selected"] = True
            st.rerun()
    with col_none:
        if st.button("Deselect All", use_container_width=True):
            for note in st.session_state.discovered_notes:
                note["selected"] = False
            st.rerun()
    with col_clear:
        if st.button("Clear List", use_container_width=True):
            st.session_state.discovered_notes = []
            st.rerun()

    # Create dataframe for display
    import pandas as pd

    df_data = []
    for i, note in enumerate(st.session_state.discovered_notes):
        df_data.append({
            "Select": note["selected"],
            "Filename": note["file_name"],
            "Folder": note["source_folder"],
            "Status": note["status"],
            "_index": i,
        })

    df = pd.DataFrame(df_data)

    # Editable data table
    edited_df = st.data_editor(
        df,
        column_config={
            "Select": st.column_config.CheckboxColumn("Select", default=True),
            "Filename": st.column_config.TextColumn("Filename", disabled=True),
            "Folder": st.column_config.TextColumn("Folder", disabled=True),
            "Status": st.column_config.TextColumn("Status", disabled=True),
            "_index": None,  # Hide index column
        },
        hide_index=True,
        use_container_width=True,
        key="note_selection_editor",
    )

    # Update session state from edited dataframe
    for _, row in edited_df.iterrows():
        idx = int(row["_index"])
        st.session_state.discovered_notes[idx]["selected"] = row["Select"]

    # Count selected
    selected_count = sum(1 for n in st.session_state.discovered_notes if n["selected"])
    total_count = len(st.session_state.discovered_notes)
    st.info(f"Selected: **{selected_count}** of {total_count} notes")

    # Process Selected button
    if selected_count > 0:
        if st.button(f"Process {selected_count} Selected Notes", type="primary", use_container_width=True):
            # Insert only selected notes into database
            inserted = 0
            for note in st.session_state.discovered_notes:
                if note["selected"]:
                    upsert_note(
                        file_path=note["file_path"],
                        file_name=note["file_name"],
                        file_modified_at=note["file_modified_at"],
                        source_folder=note["source_folder"],
                        output_folder=note["output_folder"],
                        file_hash=note["file_hash"],
                        file_size_bytes=note["file_size_bytes"],
                    )
                    inserted += 1

            # Clear discovered notes after inserting
            st.session_state.discovered_notes = []
            st.success(f"Inserted {inserted} notes into queue. Processing will start below.")
            st.rerun()
    else:
        st.warning("No notes selected. Use checkboxes above to select notes to process.")

# ============================================================================
# Process Pending Notes
# ============================================================================
st.divider()
st.subheader("3. Process Pending Notes")

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

    # Check if abort flag exists (from previous abort request)
    abort_exists = check_abort_flag()

    # Button row: Process and Abort
    col_process, col_abort = st.columns([2, 1])

    with col_process:
        process_btn = st.button(
            f"🚀 Process {pending_count} Notes",
            type="primary",
            use_container_width=True,
        )

    with col_abort:
        if st.button("⛔ Abort", type="secondary", use_container_width=True):
            set_abort_flag()
            st.warning("Abort flag set - processing will stop after current note.")
            st.rerun()

    # Show abort status
    if abort_exists:
        st.warning("⚠️ Abort flag is set. Clear it before processing or it will stop immediately.")
        if st.button("Clear Abort Flag"):
            clear_abort_flag()
            st.success("Abort flag cleared.")
            st.rerun()

    if process_btn:
        # Clear abort flag before starting
        clear_abort_flag()
        st.session_state.processing_logs = []

        # Progress container
        progress_bar = st.progress(0)
        status_text = st.empty()
        detail_text = st.empty()
        log_expander = st.expander("📋 Processing Logs (live)", expanded=True)
        log_area = log_expander.empty()

        def progress_callback(stage: str, current: int, total: int, note_name: str):
            """Update UI progress."""
            if stage == "processing":
                percent = int((current / total) * 100)
                progress_bar.progress(percent)
                status_text.markdown(f"**Processing {current}/{total}:** `{note_name}`")
            elif stage == "complete":
                progress_bar.progress(100)
                status_text.success("Processing complete!")
                detail_text.empty()  # Clear detail message on completion
            elif stage == "aborted":
                progress_bar.progress(int((current / total) * 100) if total > 0 else 0)
                status_text.warning(f"Processing aborted after {current}/{total} notes")
                detail_text.empty()

        def detail_callback(message: str):
            """Update detailed status message."""
            detail_text.markdown(f"↳ _{message}_")

        def log_callback(message: str):
            """Collect log messages."""
            timestamp = datetime.now().strftime("%H:%M:%S")
            st.session_state.processing_logs.append(f"[{timestamp}] {message}")
            # Update log display (show last 100 lines)
            log_area.code("\n".join(st.session_state.processing_logs[-100:]), language=None)

        # Run processing
        with st.status("Processing pipeline running...", expanded=True) as status:
            result = process_pending_notes(
                progress_callback=progress_callback,
                detail_callback=detail_callback,
                log_callback=log_callback,
                abort_check=check_abort_flag,
            )

            # Clear abort flag after processing
            clear_abort_flag()

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

            if result.aborted:
                status.update(label="Processing Aborted", state="error")
                st.warning("Processing was aborted by user.")
            else:
                status.update(label="Processing Complete", state="complete")
                st.success("Batch processing finished!")

        if result.review_queued > 0:
            st.info(f"👉 {result.review_queued} notes queued for review. Go to **Review** page.")

        # Show final logs
        if st.session_state.processing_logs:
            with st.expander("📋 Full Processing Log", expanded=False):
                st.code("\n".join(st.session_state.processing_logs), language=None)

        # Rerun to update pending count
        time.sleep(2)
        st.rerun()
