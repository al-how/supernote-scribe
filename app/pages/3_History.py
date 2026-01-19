"""History page for viewing processed notes."""

import streamlit as st
import pandas as pd
from pathlib import Path
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.database import (
    get_notes_history,
    get_extractions_for_note,
    update_extraction_text,
    move_note_to_review,
    reset_note_for_reprocessing,
    init_db,
)
from app.services.markdown import approve_and_save_note
import app.styles as styles

# Initialize DB
init_db()

# Initialize session state for edit mode and rescan
if "editing_note_id" not in st.session_state:
    st.session_state.editing_note_id = None
if "confirm_rescan_history" not in st.session_state:
    st.session_state.confirm_rescan_history = None

st.set_page_config(page_title="History", page_icon="📜", layout="wide")
styles.load_css()

st.title("📜 History")

# ============================================================================
# Filters
# ============================================================================
with st.expander("🔎 Search & Filter", expanded=True):
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        search_term = st.text_input("Search Filename", placeholder="e.g. 20260107")
    
    with col2:
        status_filter = st.multiselect(
            "Status",
            options=["approved", "auto_approved", "completed", "error", "pending", "review", "rejected"],
            default=["approved", "auto_approved", "rejected"]
        )
    
    with col3:
        limit = st.number_input("Limit", min_value=10, max_value=500, value=50)

# ============================================================================
# Data Loading
# ============================================================================
notes = get_notes_history(
    search_term=search_term if search_term else None,
    status_filter=status_filter if status_filter else None,
    limit=limit
)

if not notes:
    st.info("No notes found matching criteria.")
    st.stop()

# Convert to DataFrame for display
df = pd.DataFrame(notes)

# Select columns to display
display_cols = ["id", "file_modified_at", "file_name", "source_folder", "status", "output_path"]
df_display = df[display_cols].copy()
df_display["file_modified_at"] = pd.to_datetime(df_display["file_modified_at"]).dt.strftime('%Y-%m-%d %H:%M')

# Apply styling to status column
def color_status_col(val):
    color = styles.get_status_color(val)
    return f'background-color: {color}; color: white'

# Use applymap (pandas < 2.1) or map (pandas >= 2.1)
# We'll use applymap which is generally safe for now, or try/except if needed.
# But simplest is just styling the subset.
styled_df = df_display.style.applymap(color_status_col, subset=["status"])

# ============================================================================
# List View
# ============================================================================
st.subheader(f"Found {len(notes)} Notes")

# Interactive dataframe
event = st.dataframe(
    styled_df,
    use_container_width=True,
    hide_index=True,
    selection_mode="single-row",
    on_select="rerun"
)

# ============================================================================
# Detail View
# ============================================================================
if event.selection.rows:
    idx = event.selection.rows[0]
    selected_note = notes[idx]
    note_id = selected_note['id']

    st.divider()
    st.header(f"📄 {selected_note['file_name']}")

    # Action Buttons
    action_col1, action_col2, action_col3, action_col4 = st.columns([1, 1, 1, 1])

    with action_col1:
        # For rejected and auto_approved notes: show recovery button
        if selected_note['status'] in ['rejected', 'auto_approved']:
            if st.button("↩️ Move to Review", type="primary", use_container_width=True):
                move_note_to_review(note_id)
                st.success("Note moved back to review queue!")
                st.rerun()

    with action_col2:
        # For approved/auto_approved notes: show edit button
        if selected_note['status'] in ['approved', 'auto_approved']:
            if st.session_state.editing_note_id == note_id:
                if st.button("❌ Cancel Edit", use_container_width=True):
                    st.session_state.editing_note_id = None
                    st.rerun()
            else:
                if st.button("✏️ Edit", type="primary", use_container_width=True):
                    st.session_state.editing_note_id = note_id
                    st.rerun()

    with action_col3:
        # Rescan button - available for all statuses
        if st.session_state.confirm_rescan_history == note_id:
            st.warning("Re-OCR this note?")
            conf_col1, conf_col2 = st.columns(2)
            with conf_col1:
                if st.button("Yes, Rescan", type="primary", use_container_width=True, key="confirm_rescan_yes"):
                    reset_note_for_reprocessing(note_id)
                    st.session_state.confirm_rescan_history = None
                    st.session_state.editing_note_id = None
                    st.success("Note queued for rescan! Go to Scan page to process.")
                    st.rerun()
            with conf_col2:
                if st.button("Cancel", use_container_width=True, key="cancel_rescan_history"):
                    st.session_state.confirm_rescan_history = None
                    st.rerun()
        else:
            if st.button("🔄 Rescan", use_container_width=True):
                st.session_state.confirm_rescan_history = note_id
                st.rerun()

    st.divider()

    # Edit Mode
    if st.session_state.editing_note_id == note_id:
        st.subheader("Edit Mode")
        extractions = get_extractions_for_note(note_id)

        if not extractions:
            st.error("No extractions found for this note.")
        else:
            # Use tabs for multi-page notes
            if len(extractions) > 1:
                edit_tabs = st.tabs([f"Page {i+1}" for i in range(len(extractions))])
            else:
                edit_tabs = [st.container()]

            # Dictionary to hold current text values
            current_texts = {}

            for i, (tab, ext) in enumerate(zip(edit_tabs, extractions)):
                with tab:
                    edit_col1, edit_col2 = st.columns([1, 1])

                    with edit_col1:
                        st.markdown("**Original Image**")
                        if ext["png_cache_path"] and Path(ext["png_cache_path"]).exists():
                            st.image(ext["png_cache_path"], use_container_width=True)
                        else:
                            st.warning("⚠️ Image not found in cache.")

                    with edit_col2:
                        st.markdown(f"**Text (Page {i+1})**")

                        # Initial value: edited_text if exists, else raw_text
                        initial_value = ext["edited_text"] if ext["edited_text"] is not None else ext["raw_text"]

                        # Text Area
                        text_key = f"edit_text_{ext['id']}"
                        val = st.text_area(
                            "Edit Text",
                            value=initial_value,
                            height=600,
                            key=text_key,
                            label_visibility="collapsed"
                        )
                        current_texts[ext['id']] = val

            # Save Changes Button
            st.divider()
            save_col1, save_col2 = st.columns([1, 2])

            with save_col1:
                if st.button("💾 Save Changes", type="primary", use_container_width=True):
                    try:
                        # Update all extractions
                        for ext_id, text in current_texts.items():
                            update_extraction_text(ext_id, text)

                        # Regenerate markdown and update to 'approved' status
                        out_path = approve_and_save_note(note_id)

                        st.success(f"Changes saved to: `{out_path}`")
                        st.session_state.editing_note_id = None
                        st.rerun()

                    except Exception as e:
                        st.error(f"Failed to save changes: {e}")

    else:
        # Normal Detail View (not editing)
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("**Metadata**")
            st.json({
                "Source": selected_note["file_path"],
                "Output": selected_note["output_path"],
                "Processed": selected_note["processed_at"],
                "Approved": selected_note["approved_at"],
                "Status": selected_note["status"]
            })

            # Link to open file (if local) - usually not possible in browser but we can show path
            if selected_note["output_path"]:
                 st.info(f"Output saved to: `{selected_note['output_path']}`")

        with col2:
            st.markdown("**Content Preview**")
            if selected_note["output_path"] and Path(selected_note["output_path"]).exists():
                try:
                    content = Path(selected_note["output_path"]).read_text(encoding="utf-8")
                    st.code(content, language="markdown", line_numbers=False)
                except Exception as e:
                    st.error(f"Could not read file: {e}")
            else:
                st.warning("Output file not found (moved or deleted).")

