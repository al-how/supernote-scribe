from app.services import processor
from app.services.processor import ProcessResult


def test_process_pending_notes_invokes_heartbeat_and_current_note_callbacks(monkeypatch):
    notes = [
        {"id": 1, "file_name": "first.note"},
        {"id": 2, "file_name": "second.note"},
    ]
    current_notes = []
    heartbeats = []

    monkeypatch.setattr(processor, "get_pending_notes", lambda: notes)
    monkeypatch.setattr(
        processor,
        "process_single_note",
        lambda note_id, **kwargs: ProcessResult(
            note_id=note_id,
            status="review",
            page_count=1,
            char_count=10,
            output_path=None,
        ),
    )
    monkeypatch.setattr(processor, "log_activity", lambda *args, **kwargs: None)

    result = processor.process_pending_notes(
        heartbeat_callback=lambda: heartbeats.append("beat"),
        current_note_callback=lambda note: current_notes.append(note),
    )

    assert result.processed == 2
    assert heartbeats == ["beat", "beat"]
    assert current_notes == [notes[0], notes[1], None]


def test_process_pending_notes_clears_current_note_when_processing_raises(monkeypatch):
    notes = [{"id": 1, "file_name": "first.note"}]
    current_notes = []

    monkeypatch.setattr(processor, "get_pending_notes", lambda: notes)

    def fail_processing(note_id, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(processor, "process_single_note", fail_processing)

    try:
        processor.process_pending_notes(
            current_note_callback=lambda note: current_notes.append(note),
        )
    except RuntimeError:
        pass

    assert current_notes == [notes[0], None]
