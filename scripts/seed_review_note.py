"""Seed one note in 'review' status with a 2-page extraction for UI testing."""

from datetime import datetime, timezone
from pathlib import Path

from app.database import (
    get_connection,
    init_db,
    insert_extraction,
    insert_note,
    mark_note_for_review,
)


def seed():
    """Create a deterministic local Review Queue fixture."""
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    fpath = "/data/source/_fixtures/Sample Review Note.note"

    with get_connection() as conn:
        conn.execute("DELETE FROM notes WHERE file_path = ?", (fpath,))

    note_id = insert_note(
        file_path=fpath,
        file_name="Sample Review Note.note",
        file_modified_at=now,
        source_folder="Other",
        output_folder="Journals/Other/",
        page_count=2,
    )

    sample_png = next(Path("data/png_cache").rglob("*.png"), None)
    png = str(sample_png) if sample_png else None

    insert_extraction(
        note_id,
        1,
        "# Heading\n\nShort body with <b>HTML</b> & symbols.",
        ai_model="llama_server",
        png_cache_path=png,
        ai_response_time_ms=3200,
    )
    insert_extraction(
        note_id,
        2,
        "Page two text.\n\n- bullet\n- bullet",
        ai_model="openai",
        png_cache_path=png,
        ai_response_time_ms=1500,
    )
    mark_note_for_review(note_id)
    print(f"Seeded review note id={note_id}")


if __name__ == "__main__":
    seed()
