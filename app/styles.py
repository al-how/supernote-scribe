import streamlit as st

def load_css():
    """Inject shared CSS styles."""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap');

    /* Monospace for technical inputs */
    .stTextInput input, .stNumberInput input, code {
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    /* Dashboard Metric Cards */
    [data-testid="metric-container"] {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 8px;
        padding: 16px;
    }
    </style>
    """, unsafe_allow_html=True)

def get_status_color(status: str) -> str:
    """Return color hex for a given status."""
    colors = {
        "approved": "#22c55e",      # green
        "auto_approved": "#3b82f6", # blue
        "review": "#f59e0b",        # amber
        "error": "#ef4444",         # red
        "pending": "#6b7280",       # gray
    }
    return colors.get(status, "#6b7280")

def status_badge_html(status: str) -> str:
    """Return HTML string for status badge (for Markdown/HTML displays)."""
    color = get_status_color(status)
    return f'<span style="background:{color}; padding:2px 8px; border-radius:4px; font-size:12px; color:white;">{status}</span>'
