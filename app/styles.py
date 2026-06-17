import html

import pandas as pd
import streamlit as st

def load_css():
    """Inject shared CSS styles."""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap');

    /* Monospace only for technical text */
    code, pre, kbd, [data-testid="stCodeBlock"], input[type="password"] {
        font-family: 'JetBrains Mono', monospace !important;
    }

    h1, h2, h3 {
        font-weight: 650 !important;
        letter-spacing: 0 !important;
    }

    h1 {
        padding-bottom: 0.25rem;
    }
    
    /* Dashboard Metric Cards */
    [data-testid="metric-container"] {
        background: rgba(255,255,255,0.055);
        border: 1px solid rgba(255,255,255,0.16);
        border-radius: 8px;
        padding: 16px 18px;
        box-shadow: 0 10px 28px rgba(0,0,0,0.18);
    }

    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 1.9rem;
        font-weight: 700;
    }

    .stButton button {
        border-radius: 8px;
        transition: background-color 140ms ease, border-color 140ms ease, transform 140ms ease;
    }

    .stButton button:hover {
        cursor: pointer;
        border-color: rgba(59,130,246,0.72);
        transform: translateY(-1px);
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

def style_status_column(df, column: str = "status"):
    """Apply status colors to a pandas dataframe status column."""
    def color_status_col(val):
        color = get_status_color(val)
        return f"background-color: {color}; color: white"

    styler = df.style
    if hasattr(styler, "map"):
        return styler.map(color_status_col, subset=[column])
    return styler.applymap(color_status_col, subset=[column])

def format_datetime_series(series, display_format: str = "%Y-%m-%d %H:%M"):
    """Format mixed ISO datetime strings for table display."""
    parsed = pd.to_datetime(series, format="mixed", errors="coerce", utc=True)
    return parsed.dt.strftime(display_format)

def status_badge_html(status: str) -> str:
    """Return HTML string for status badge (for Markdown/HTML displays)."""
    color = get_status_color(status)
    safe_status = html.escape(str(status))
    return f'<span style="background:{color}; padding:2px 8px; border-radius:4px; font-size:12px; color:white;">{safe_status}</span>'

def metadata_panel(items: dict) -> str:
    """Return escaped HTML for compact label/value metadata rows."""
    rows = []
    for label, value in items.items():
        safe_label = html.escape(str(label))
        safe_value = html.escape("" if value is None else str(value))
        rows.append(
            "<div style=\"display:flex; justify-content:space-between; gap:16px; "
            "padding:4px 0; border-bottom:1px solid rgba(255,255,255,0.08);\">"
            f"<span style=\"color:#9ca3af;\">{safe_label}</span>"
            f"<span style=\"font-weight:600; text-align:right;\">{safe_value}</span>"
            "</div>"
        )
    return (
        "<div style=\"border:1px solid rgba(255,255,255,0.12); border-radius:8px; "
        "padding:10px 12px; background:rgba(255,255,255,0.04);\">"
        + "".join(rows)
        + "</div>"
    )
