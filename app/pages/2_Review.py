"""Review page for verifying and editing extracted text."""

import streamlit as st
import asyncio
from pathlib import Path

from app.database import (
    get_review_queue,
    get_extractions_for_note,
    update_extraction_text,
    mark_note_for_review,
    delete_note,
    init_db,
)
from app.services.markdown import approve_and_save_note
import app.styles as styles

# Initialize DB
init_db()

st.set_page_config(page_title="Review Queue", page_icon="✏️", layout="wide")
styles.load_css()

st.title("✏️ Review Queue")

# 1. Fetch Review Queue
queue = get_review_queue()

if not queue:
    st.markdown("""
    <div style="text-align:center; padding:40px;">
        <div style="font-size:48px;">✨</div>
        <h3>All caught up!</h3>
        <p style="color:#888;">No notes waiting for review</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("Refresh Queue"):
        st.rerun()
    st.stop()

# 2. Select Note
# Map display names to note objects
note_options = {f"{n['file_name']} ({n['source_folder']})": n for n in queue}
selected_option = st.sidebar.selectbox(
    "Select Note to Review",
    options=list(note_options.keys()),
    index=0
)
selected_note = note_options[selected_option]
note_id = selected_note["id"]

# 3. Load Extractions (Pages)
extractions = get_extractions_for_note(note_id)

if not extractions:
    st.error("⚠️ Note has no extracted pages. It might have failed processing.")
    if st.button("Delete Note"):
        delete_note(note_id)
        st.rerun()
    st.stop()

st.header(f"📄 {selected_note['file_name']}")
st.caption(f"Path: {selected_note['file_path']}")

# 4. Review Interface
# Use tabs for multi-page notes
if len(extractions) > 1:
    tabs = st.tabs([f"Page {i+1}" for i in range(len(extractions))])
else:
    tabs = [st.container()]

# Dictionary to hold current text values
current_texts = {}

for i, (tab, ext) in enumerate(zip(tabs, extractions)):
    with tab:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("**Original Image**")
            if ext["png_cache_path"] and Path(ext["png_cache_path"]).exists():
                st.image(ext["png_cache_path"], use_container_width=True)
            else:
                st.warning("⚠️ Image not found in cache.")

        with col2:
            st.markdown(f"**Extracted Text (Page {i+1})**")
            st.caption(f"Model: {ext['ai_model']} | Confidence: N/A")
            
            # Key for session state
            text_key = f"text_{ext['id']}"
            
            # Initial value: edited_text if exists, else raw_text
            initial_value = ext["edited_text"] if ext["edited_text"] is not None else ext["raw_text"]
            
            # Text Area
            val = st.text_area(
                "Edit Text",
                value=initial_value,
                height=600,
                key=text_key,
                label_visibility="collapsed"
            )
            current_texts[ext['id']] = val

# 5. Actions Bar
st.divider()
col_actions, col_info = st.columns([2, 1])

with col_actions:
    c1, c2, c3 = st.columns(3)
    
    with c1:
        if st.button("✅ Approve & Save", type="primary", use_container_width=True):
            try:
                # 1. Save all current edits to DB
                for ext_id, text in current_texts.items():
                    update_extraction_text(ext_id, text)
                
                # 2. Generate Markdown and Mark Approved
                out_path = approve_and_save_note(note_id)
                
                st.success(f"Saved to: `{out_path}`")
                st.balloons()
                
                # Wait a bit then refresh
                st.rerun()
                
            except Exception as e:
                st.error(f"Failed to approve: {e}")

    with c2:
        if st.button("💾 Save Draft", use_container_width=True):
            # Just update DB
            for ext_id, text in current_texts.items():
                update_extraction_text(ext_id, text)
            st.toast("Draft saved!")

    with c3:
        if st.button("🗑️ Delete/Reject", type="secondary", use_container_width=True):
            if st.button("Confirm Delete?", type="primary"):
                delete_note(note_id)
                st.success("Note deleted.")
                st.rerun()

with col_info:
    st.markdown(f"""
    **Output Info:**
    - Folder: `{selected_note['output_folder']}`
    - Status: `{selected_note['status']}`
    """)
