# UI Polish Plan

**Status**: Draft - awaiting user decision
**Created**: 2026-01-16
**Context**: Design feedback after completing Step 8 (Markdown service)

## Summary

The Streamlit app is functional with good information architecture. Currently uses default Streamlit styling. This plan outlines optional UI improvements before proceeding to Step 10 (Docker config).

## Current State

- Dark theme (Streamlit default)
- Standard components and fonts
- Coral/salmon primary buttons
- Emoji icons for section headers
- Clear hierarchy and logical navigation

## Proposed Improvements

### Priority 1: Quick Wins (30 min)

#### 1.1 Custom Typography
Add monospace font for technical values (paths, URLs, model names).

```python
# Add to each page or create shared styles.py
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap');

/* Monospace for technical inputs */
.stTextInput input, .stNumberInput input, code {
    font-family: 'JetBrains Mono', monospace !important;
}
</style>
""", unsafe_allow_html=True)
```

#### 1.2 Status Badges in History
Replace plain text status with colored badges.

```python
def status_badge(status: str) -> str:
    colors = {
        "approved": "#22c55e",      # green
        "auto_approved": "#3b82f6", # blue
        "review": "#f59e0b",        # amber
        "error": "#ef4444",         # red
        "pending": "#6b7280",       # gray
    }
    color = colors.get(status, "#6b7280")
    return f'<span style="background:{color}; padding:2px 8px; border-radius:4px; font-size:12px;">{status}</span>'
```

### Priority 2: Visual Polish (1 hr)

#### 2.1 Dashboard Metric Cards
Add subtle card backgrounds to Status Overview numbers.

```python
st.markdown("""
<style>
[data-testid="metric-container"] {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    padding: 16px;
}
</style>
""", unsafe_allow_html=True)
```

#### 2.2 Improved Empty States
Add more personality to empty states (Review Queue, no pending notes).

```python
# Instead of just st.success("All caught up!")
st.markdown("""
<div style="text-align:center; padding:40px;">
    <div style="font-size:48px;">✨</div>
    <h3>All caught up!</h3>
    <p style="color:#888;">No notes waiting for review</p>
</div>
""", unsafe_allow_html=True)
```

### Priority 3: Nice to Have (2+ hrs)

- Alternating row colors in History table
- Custom color accent theme (amber/teal instead of coral)
- Animated progress indicators during processing
- Subtle hover effects on buttons

## Files to Modify

| File | Changes |
|------|---------|
| `app/Home.py` | Metric card styling, shared CSS import |
| `app/pages/2_Review.py` | Empty state enhancement |
| `app/pages/3_History.py` | Status badges, table styling |
| `app/pages/4_Settings.py` | Monospace font for path inputs |
| (new) `app/styles.py` | Shared CSS and helper functions |

## Decision Points

1. **Implement now or skip?** - The app works fine as-is. These are cosmetic improvements.
2. **If implementing, which priority level?**
   - P1 only (30 min)
   - P1 + P2 (1.5 hrs)
   - All (3+ hrs)
3. **Create shared styles module?** - Keeps CSS DRY but adds a file.

## Recommendation

For a personal utility tool, **P1 only** provides the best value:
- Monospace fonts make paths more readable
- Status badges improve History page scanability
- Minimal time investment before Docker deployment

Skip P2/P3 unless you plan to share this tool with others.

## Next Steps After This

- Step 10: Docker config (Dockerfile, docker-compose.yml)
- Step 11: Local testing with sample .note files
- Step 12: Deploy to Unraid
