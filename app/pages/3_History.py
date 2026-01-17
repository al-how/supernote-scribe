"""History page for viewing processed notes."""

import streamlit as st
import pandas as pd
from pathlib import Path
from app.database import get_notes_history, init_db
import app.styles as styles

# Initialize DB
init_db()

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
            options=["approved", "auto_approved", "completed", "error", "pending", "review"],
            default=["approved", "auto_approved"]
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
    
    st.divider()
    st.header(f"📄 {selected_note['file_name']}")
    
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
                st.text_area("Markdown Content", value=content, height=400)
            except Exception as e:
                st.error(f"Could not read file: {e}")
        else:
            st.warning("Output file not found (moved or deleted).")

