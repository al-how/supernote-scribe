"""Review page for verifying and editing extracted text."""

from pathlib import Path
import os
import sys

import streamlit as st

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.database import (
    get_extractions_for_note,
    get_review_queue,
    init_db,
    mark_note_rejected,
    reset_note_for_reprocessing,
    update_extraction_text,
)
from app.services.markdown import approve_and_save_note
import app.styles as styles


def clear_confirmation_state() -> None:
    """Clear armed destructive-action confirmations."""
    st.session_state.confirm_delete = None
    st.session_state.confirm_rescan = None


def set_review_index(index: int) -> None:
    """Set current queue position and clear note-scoped confirmations."""
    if index != st.session_state.review_index:
        st.session_state.review_index = index
        clear_confirmation_state()


def format_response_time(milliseconds: int | None) -> str:
    """Format an OCR response time for compact display."""
    if milliseconds is None:
        return "response time unavailable"
    return f"{milliseconds / 1000:.1f}s"


def extraction_metadata_html(ext: dict) -> str:
    """Build escaped HTML for page-level OCR metadata."""
    model_badge = styles.status_badge_html(ext.get("ai_model", "unknown"))
    char_count = ext.get("char_count") or 0
    response_time = format_response_time(ext.get("ai_response_time_ms"))
    return (
        "<div style=\"display:flex; flex-wrap:wrap; gap:8px; align-items:center; "
        "margin:4px 0 12px 0;\">"
        f"{model_badge}"
        f"<span style=\"color:#9ca3af; font-size:12px;\">{char_count} chars</span>"
        f"<span style=\"color:#9ca3af; font-size:12px;\">{response_time}</span>"
        "</div>"
    )


# Initialize DB
init_db()

# Initialize session state
if "confirm_delete" not in st.session_state:
    st.session_state.confirm_delete = None
if "confirm_rescan" not in st.session_state:
    st.session_state.confirm_rescan = None
if "review_index" not in st.session_state:
    st.session_state.review_index = 0
if "selected_review_note_id" not in st.session_state:
    st.session_state.selected_review_note_id = None

st.set_page_config(page_title="Review Queue", page_icon="Review", layout="wide")
styles.load_css()

st.title("Review Queue")

# 1. Fetch Review Queue
queue = get_review_queue()

if queue:
    max_index = len(queue) - 1
    if st.session_state.review_index > max_index:
        st.session_state.review_index = max_index
    if st.session_state.review_index < 0:
        st.session_state.review_index = 0

if not queue:
    st.markdown("""
    <div style="text-align:center; padding:40px;">
        <div style="font-size:48px;">*</div>
        <h3>All caught up!</h3>
        <p style="color:#888;">No notes waiting for review</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Refresh Queue"):
        st.rerun()
    st.stop()

# 2. Select Note
note_options = [f"{n['file_name']} ({n['source_folder']})" for n in queue]

selected_option = st.sidebar.selectbox(
    "Select Note to Review",
    options=note_options,
    index=st.session_state.review_index,
)
selected_option_index = note_options.index(selected_option)
if selected_option_index != st.session_state.review_index:
    set_review_index(selected_option_index)
    st.rerun()

selected_note = queue[st.session_state.review_index]
note_id = selected_note["id"]

if st.session_state.selected_review_note_id != note_id:
    clear_confirmation_state()
    st.session_state.selected_review_note_id = note_id

top_left, top_right = st.columns([3, 2])
with top_left:
    st.subheader(selected_note["file_name"])
    st.caption(f"Path: {selected_note['file_path']}")
with top_right:
    st.markdown(
        f"<div style=\"text-align:right; font-weight:600;\">"
        f"Note {st.session_state.review_index + 1} of {len(queue)}</div>",
        unsafe_allow_html=True,
    )
    st.progress((st.session_state.review_index + 1) / len(queue))

nav_prev, nav_next, nav_spacer = st.columns([1, 1, 5])
with nav_prev:
    if st.button("Prev", disabled=st.session_state.review_index == 0, use_container_width=True):
        set_review_index(st.session_state.review_index - 1)
        st.rerun()
with nav_next:
    if st.button(
        "Next",
        disabled=st.session_state.review_index >= len(queue) - 1,
        use_container_width=True,
    ):
        set_review_index(st.session_state.review_index + 1)
        st.rerun()

# 3. Load Extractions (Pages)
extractions = get_extractions_for_note(note_id)

if not extractions:
    st.error("Note has no extracted pages. It might have failed processing.")
    if st.button("Reject Note"):
        mark_note_rejected(note_id)
        st.rerun()
    st.stop()

# 4. Review Interface
if len(extractions) > 1:
    tabs = st.tabs([f"Page {i + 1}" for i in range(len(extractions))])
else:
    tabs = [st.container()]

current_texts = {}

for i, (tab, ext) in enumerate(zip(tabs, extractions)):
    with tab:
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("**Original Image**")
            png_path = ext["png_cache_path"]
            if png_path and Path(png_path).exists():
                st.image(png_path, use_container_width=True)
                with st.expander("View full size"):
                    st.image(png_path, use_container_width=True)
            else:
                st.warning("Image not found in cache.")

        with col2:
            st.markdown(f"**Extracted Text (Page {i + 1})**")
            st.markdown(extraction_metadata_html(ext), unsafe_allow_html=True)

            text_key = f"text_{ext['id']}"
            initial_value = (
                ext["edited_text"] if ext["edited_text"] is not None else ext["raw_text"]
            )

            edit_tab, preview_tab = st.tabs(["Edit", "Preview"])
            with edit_tab:
                val = st.text_area(
                    "Edit Text",
                    value=initial_value,
                    height=600,
                    key=text_key,
                    label_visibility="collapsed",
                )
            with preview_tab:
                preview_text = st.session_state.get(text_key, initial_value)
                st.markdown(preview_text or "_No text to preview._")

            current_texts[ext["id"]] = st.session_state.get(text_key, initial_value)

# 5. Actions Bar
st.divider()
col_actions, col_info = st.columns([2, 1])

with col_actions:
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        if st.button("Approve & Next", type="primary", use_container_width=True):
            try:
                for ext_id, text in current_texts.items():
                    update_extraction_text(ext_id, text)

                approve_and_save_note(note_id)
                clear_confirmation_state()
                st.rerun()

            except Exception as e:
                st.error(f"Failed to approve: {e}")

    with c2:
        if st.button("Save Draft", use_container_width=True):
            for ext_id, text in current_texts.items():
                update_extraction_text(ext_id, text)
            st.toast("Draft saved")

    with c3:
        if st.session_state.confirm_rescan == note_id:
            st.warning("Re-OCR this note?")
            conf_col1, conf_col2 = st.columns(2)
            with conf_col1:
                if st.button("Yes, Rescan", type="primary", use_container_width=True):
                    reset_note_for_reprocessing(note_id)
                    clear_confirmation_state()
                    st.toast("Note queued for rescan")
                    st.rerun()
            with conf_col2:
                if st.button("Cancel", use_container_width=True, key="cancel_rescan"):
                    clear_confirmation_state()
                    st.rerun()
        elif st.button("Rescan", use_container_width=True):
            st.session_state.confirm_rescan = note_id
            st.rerun()

    with c4:
        if st.session_state.confirm_delete == note_id:
            st.warning("Are you sure?")
            conf_col1, conf_col2 = st.columns(2)
            with conf_col1:
                if st.button("Yes, Reject", type="primary", use_container_width=True):
                    mark_note_rejected(note_id)
                    clear_confirmation_state()
                    st.toast("Note rejected")
                    st.rerun()
            with conf_col2:
                if st.button("Cancel", use_container_width=True, key="cancel_reject"):
                    clear_confirmation_state()
                    st.rerun()
        elif st.button("Reject", type="secondary", use_container_width=True):
            st.session_state.confirm_delete = note_id
            st.rerun()

with col_info:
    st.markdown("**Output Info**")
    st.markdown(
        styles.metadata_panel(
            {
                "Folder": selected_note["output_folder"],
                "Status": selected_note["status"],
            }
        ),
        unsafe_allow_html=True,
    )
