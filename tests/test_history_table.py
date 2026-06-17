"""Tests for History page table styling helpers."""

import pandas as pd

from app import styles


def test_status_column_styling_uses_pandas_map_when_applymap_is_unavailable(monkeypatch):
    """History status styling works with pandas versions that removed Styler.applymap."""
    df = pd.DataFrame({"status": ["approved"], "file_name": ["note.note"]})
    styler_type = type(df.style)

    monkeypatch.delattr(styler_type, "applymap", raising=False)

    styled = styles.style_status_column(df)
    html = styled.to_html()

    assert type(styled).__name__ == "Styler"
    assert "background-color: #22c55e;" in html
    assert "color: white;" in html


def test_format_datetime_series_accepts_mixed_iso_timezone_values():
    """History table dates support seeded UTC timestamps and older naive values."""
    values = pd.Series([
        "2026-01-16T15:57:50.283494+00:00",
        "2026-01-16T15:57:50.283494",
    ])

    formatted = styles.format_datetime_series(values)

    assert list(formatted) == ["2026-01-16 15:57", "2026-01-16 15:57"]
