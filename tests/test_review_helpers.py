"""Tests for Review page HTML helper safety."""

import app.styles as styles


def test_status_badge_escapes():
    out = styles.status_badge_html("<script>alert(1)</script>")

    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_metadata_panel_escapes_values():
    out = styles.metadata_panel({"File": 'a<b>&"c'})

    assert "<b>" not in out
    assert "&lt;b&gt;" in out
