# Plan: Review Workflow Overhaul + Visual Polish

> Scoped implementation plan for the first committed slice of the broader
> [UX/UI Improvement Backlog](ux-ui-improvements.md). Covers two areas: a comprehensive
> overhaul of the Review Queue, and an app-wide visual/theme polish. No backend, schema,
> OCR, deployment, or automation behavior changes.

## Context

The Supernote Converter is fully functional but looks and feels like a stock Streamlit app.
The backend already collects rich per-page data (char counts, which model handled each page,
OCR response time) and exposes it via `get_extractions_for_note` (`SELECT *`), but the UI
hides almost all of it.

Two areas give the most return:

1. **Review Queue** (`app/pages/2_Review.py`) is the highest-frequency screen. Today every
   approval bounces you back to a sidebar dropdown to pick the next note, there is no sense
   of how many notes remain, the metadata line shows a useless `Confidence: N/A`, and there
   is no rendered-markdown preview of edits.
2. **Visual identity** is minimal — `app/styles.py` is ~22 lines and there is no
   `.streamlit/config.toml`, so the app uses default Streamlit theming. (Note: the current
   `styles.py` already assumes a dark background — metric cards use white-on-transparent —
   so a light-mode browser currently renders a half-broken UI.)

Goal: a comprehensive but low-risk overhaul of these two areas. We only surface data that
already exists and reuse existing DB functions.

## Staging

The work is split into two sequenced stages to keep the blast radius small. **Ship Stage 1
first, see it live, then do Stage 2.**

Stage 1 is self-contained: it includes the **minimal** `app/styles.py` work it depends on
(the `metadata_panel()` helper and HTML-escaping of `status_badge_html()`), so Stage 1 can
finish and pass its gates without Stage 2. Stage 2 is the broader, purely visual theme polish
(`.streamlit/config.toml`, font scoping, card/button/typography) that has no functional
dependency the other way.

- **Stage 1 — Review Queue overhaul** (`app/pages/2_Review.py`) + minimal `app/styles.py`
  helpers (`metadata_panel()`, escaped `status_badge_html()`)
- **Stage 2 — Visual theme & polish** (`.streamlit/config.toml`, broader `app/styles.py`)

Bump `__version__` in `app/__init__.py` to `0.3.0` (per project rule: always update the
version when committing changes).

---

## Stage 1 — Review Queue overhaul (`app/pages/2_Review.py`)

Reuses existing DB functions only: `get_review_queue`, `get_extractions_for_note`,
`update_extraction_text`, `mark_note_for_review`, `mark_note_rejected`,
`reset_note_for_reprocessing`, and `approve_and_save_note`.

### 1.1 Queue position + navigation (replaces sidebar-only selection)
- Track current position in `st.session_state.review_index` (default 0).
- **Re-clamp `review_index` to `len(queue)-1` after every `get_review_queue()` call**, since
  approve/rescan/reject all shrink the queue. This prevents an out-of-range index after the
  current note leaves the queue.
- Keep the sidebar selectbox but have it set `review_index`. Add **◀ Prev / Next ▶** buttons,
  a **"Note X of N"** indicator, and a thin `st.progress` bar near the title so queue size
  is always visible.
- **Selectbox / session-state pattern (avoid the widget-state conflict).** Do not bind the
  selectbox `value` to `review_index` while *also* writing `review_index` from Prev/Next —
  Streamlit's widget state and your state will fight and cause flicker/reset loops. Instead:
  drive everything off `review_index` as the single source of truth, give the selectbox a
  fixed `key` and pass `index=st.session_state.review_index`, and in its `on_change` callback
  set `review_index` from the selected option. Prev/Next mutate `review_index` then
  `st.rerun()`. Never assign to the selectbox's own `key` in session_state after the widget
  is created.
- **Clear confirmation state when the selected note changes.** Whenever `review_index` moves
  (Prev/Next or selectbox), reset `confirm_rescan` / `confirm_delete` to `None` so an armed
  confirmation can't bleed onto a different note.
- The selected note derives from `queue[review_index]`.

### 1.2 "Approve & Next" auto-advance
- Rename the primary action to **✅ Approve & Next**. After `approve_and_save_note(note_id)`
  the note leaves the `review` queue automatically, so on `st.rerun()` the next note slides
  into the same index — no manual reselection. Index clamping (1.1) handles the last-note
  case.
- Keep **💾 Save Draft** (unchanged), **🔄 Rescan**, **🗑️ Reject** with their existing
  confirmation-via-session-state pattern. Reject/Rescan also auto-advance.
- Text areas remain keyed by extraction ID (`text_key = f"text_{ext['id']}"`, already in
  place at `app/pages/2_Review.py:104`). Extraction IDs are globally unique, so edits cannot
  bleed across notes — no change needed here, just preserve it.

### 1.3 Real metadata instead of `Confidence: N/A`
Replace the `Model: {ai_model} | Confidence: N/A` caption (`app/pages/2_Review.py:101`) with
a clean metadata strip built from data already on each extraction row:
- `ai_model` (rendered as a status-style badge),
- `char_count` chars,
- `ai_response_time_ms` shown as seconds (e.g. `3.2s`), guarded for `None`.
Render via the `styles.status_badge_html()` / new `metadata_panel()` helpers (defined in §1.7;
both must HTML-escape values — handwritten OCR text and model names are untrusted input).

### 1.4 Markdown preview of edits
For each page, add an **Edit / Preview** toggle (`st.tabs(["Edit", "Preview"])`) in the right
column. "Edit" keeps the existing 600px `text_area`; "Preview" renders the current text via
`st.markdown(...)` so formatting can be verified before approving. Read the live value from
the same `st.session_state[text_key]` the text_area uses.

### 1.5 Larger image inspection
Below the original image, add a **"🔍 View full size"** `st.expander` that re-renders the PNG
at full width. Keep the existing cache-missing warning (`app/pages/2_Review.py:94-97`).

### 1.6 Layout cleanup
- Tighter header block.
- Keep the actions/info two-column footer but render "Output Info" via the `metadata_panel`
  helper for visual consistency.

### 1.7 Minimal `app/styles.py` helpers (Stage 1's only styles work)
Stage 1 needs these two helpers to exist and be safe. Keep this work *minimal* — broader
theme polish stays in Stage 2 (§2.2).
- **Add `metadata_panel(items: dict) -> str`** returning clean HTML (label/value rows), used
  by §1.3 (page metadata strip) and §1.6 (Output Info).
- **HTML-escape all interpolated values** in both `metadata_panel()` and the existing
  `status_badge_html()` via `html.escape()`. These render through `unsafe_allow_html=True`
  over filenames, paths, model names, and OCR'd content (untrusted input). `status_badge_html()`
  currently does not escape — fix it here. This is what the §"Escaping unit test" gate asserts.

---

## Stage 2 — Visual theme & polish

### 2.1 New `.streamlit/config.toml` (theme baseline)
Create `.streamlit/config.toml` at the repo root with a dark theme so the look is consistent
app-wide without per-page CSS hacks (and so it matches what `styles.py` already assumes):

```toml
[theme]
base = "dark"
primaryColor = "#3b82f6"          # matches existing status-blue accent
backgroundColor = "#0e1117"
secondaryBackgroundColor = "#1a1d24"
textColor = "#e6e6e6"
font = "sans serif"
```

**Docker note (verified):** the `Dockerfile` copies only `app/` and `start.sh` (lines
21-22), so a repo-root `.streamlit/` will **not** reach the image. Add
`COPY .streamlit ./.streamlit` (WORKDIR is `/app`, where Streamlit looks for `.streamlit/`).

### 2.2 Rework `app/styles.py`
- **Scope the monospace font** so JetBrains Mono applies only to `code`, password/path
  fields and metadata captions — not every `stTextInput`/`stNumberInput`. Over-application
  currently makes editable text feel heavy.
- **Polish metric cards**: stronger border, subtle shadow, slightly larger value text via
  the existing `[data-testid="metric-container"]` selector.
- **Button hover states**: add a `:hover` transition (background lift + cursor) for
  `.stButton button`.
- **Typography**: tighten `h1/h2/h3` weight/letter-spacing for a less generic feel.

(The `metadata_panel()` helper and `status_badge_html()` escaping are **not** here — they ship
in Stage 1 §1.7 because Stage 1 depends on them.)

Keep all of this inside the existing `load_css()` injection so every page that already calls
`styles.load_css()` picks it up automatically (Home, Scan, Review, History, Settings all
call it).

---

## Loop-safe execution (fixtures & machine-checkable gates)

These exist so an agent has a deterministic stopping condition and does not depend on a live
OCR backend or human eyes to make progress. Visual/theme correctness still needs human
sign-off (see Verification), but everything below the agent can run and assert itself.

### Terminating condition for the agent
The implementation loop is "done" when, **without a running Ollama/llama-server**:
1. `pytest tests/test_review_helpers.py` passes (the escaping gate below), and
2. `streamlit run app/Home.py` launches and Home + Review pages load without exceptions, and
3. **a browser actually drives the Review flow** (this is UX work — a server start is not
   enough). Navigate to `http://localhost:8501/Review_Queue` (or click the sidebar "Review
   Queue" link) against the seeded fixture and assert the **visible** elements/text:
   - the "Note 1 of N" indicator and the queue progress bar,
   - the metadata strip (a model badge, a char count, a `…s` response time — and **not** the
     string "Confidence: N/A"),
   - the **Edit** and **Preview** tabs, and that switching to Preview renders markdown,
   - the "🔍 View full size" expander,
   - the **Approve & Next**, **Save Draft**, **Rescan**, **Reject** buttons,
   - clicking **Approve & Next** decrements the queue and advances without sidebar clicks.

   Use the in-IDE Browser tool or a Playwright-style script for this gate; the agent must
   confirm rendered selectors/text, not just an HTTP 200. (If no browser automation is
   available to the agent, it must stop and hand off to a human for step 3 rather than
   declare done.)

The dark-theme *appearance* (colors, fonts, spacing) and screenshots remain **human sign-off,
outside the loop** — the agent must not block on subjective visual quality, only on the
functional selectors above.

### Seed a `review`-status note (no OCR backend required)
Create `scripts/seed_review_note.py` so the agent (and a human) can produce a deterministic
review-queue note. Uses only existing DB functions (signatures verified in `app/database.py`):

```python
"""Seed one note in 'review' status with a 2-page extraction for UI testing."""
from datetime import datetime, timezone
from pathlib import Path
from app.database import (
    init_db, insert_note, insert_extraction, mark_note_for_review, get_connection,
)

def seed():
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    fpath = "/data/source/_fixtures/Sample Review Note.note"
    # idempotent: remove any prior fixture row so reruns are clean
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
    # Use any existing PNG as the cached image, or None to exercise the missing-image path.
    # rglob (recursive): the cache may store PNGs in nested note/page directories.
    sample_png = next(Path("data/png_cache").rglob("*.png"), None)
    png = str(sample_png) if sample_png else None
    insert_extraction(note_id, 1, "# Heading\n\nShort body with <b>HTML</b> & symbols.",
                      ai_model="llama_server", png_cache_path=png, ai_response_time_ms=3200)
    insert_extraction(note_id, 2, "Page two text.\n\n- bullet\n- bullet",
                      ai_model="openai", png_cache_path=png, ai_response_time_ms=1500)
    mark_note_for_review(note_id)
    print(f"Seeded review note id={note_id}")

if __name__ == "__main__":
    seed()
```

Run with `python -m scripts.seed_review_note`. The page-1 text deliberately contains `<b>`
and `&` so the agent can eyeball that escaping (§1.3 / §1.7) works. Re-running is idempotent.

> **DB safety:** this writes to the local `data/supernote.db` (the default app DB). Do **not**
> run it against the Unraid production DB (`/mnt/user/appdata/supernote-converter/supernote.db`).
> The browser-flow checks below (Approve & Next, Reject, Rescan) **mutate queue state**, so use
> a fresh or backed-up local DB for destructive verification.

### Escaping unit test (the machine-checkable gate)
Create `tests/test_review_helpers.py` asserting the HTML helpers escape untrusted input. This
is the green/red signal the loop terminates on:

```python
import app.styles as styles

def test_status_badge_escapes():
    out = styles.status_badge_html("<script>alert(1)</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out

def test_metadata_panel_escapes_values():
    out = styles.metadata_panel({"File": 'a<b>&"c'})
    assert "<b>" not in out
    assert "&lt;b&gt;" in out
```

Both helpers must therefore route every interpolated value through `html.escape()`. If
`tests/` already has a conftest/import pattern, follow it; otherwise these run from repo root
with `pytest`.

---

## Critical files

| File | Stage | Change |
|------|-------|--------|
| `app/pages/2_Review.py` | 1 | Main overhaul (queue nav, Approve & Next, metadata, preview) |
| `app/styles.py` | 1 | `metadata_panel()` helper + escape `status_badge_html()` (§1.7) |
| `app/styles.py` | 2 | Scoped fonts, card/button/typography polish (§2.2) |
| `.streamlit/config.toml` | 2 | **New** theme baseline |
| `Dockerfile` | 2 | Add `COPY .streamlit ./.streamlit` (verified missing) |
| `app/__init__.py` | 1 | Version bump to `0.3.0` |
| `scripts/seed_review_note.py` | 1 | **New** deterministic review-note fixture (loop-safe) |
| `tests/test_review_helpers.py` | 1 | **New** escaping gate the loop terminates on |

Out of scope (in the backlog, deferred to a later pass): Home health-monitor / next-action,
Scan consolidation, History filters & JSON→panel cleanup, Settings sectioning.

---

## Verification

**Stage 1 (Review):**
1. Seed test data with `python -m scripts.seed_review_note`, then run locally:
   `streamlit run app/Home.py`. (No OCR backend needed — the fixture creates the
   `review`-status note directly.) Confirm the escaping gate first: `pytest
   tests/test_review_helpers.py`.
2. "Note X of N" + progress bar show correct counts.
3. Prev/Next move through the queue; sidebar selectbox stays in sync.
4. Arm a Rescan/Reject confirmation, then navigate away — confirmation does **not** persist
   onto the next note (confirmation-state clearing).
5. Metadata strip shows real model badge, char count, and response time in seconds (no
   "Confidence: N/A").
6. Edit text, switch to Preview tab, confirm markdown renders; "View full size" enlarges the
   page image.
7. **Approve & Next** removes the note and auto-advances without touching the sidebar; the
   queue count decrements.
8. Approve the last note → "All caught up! ✨" empty state shows without errors (index clamp).
9. Sanity-check escaping: a note whose filename/text contains `<`, `>`, or `&` renders as
   literal text, not broken/injected HTML.
10. Version `0.3.0` shows on the Home page System Information expander.

**Stage 2 (theme):**
11. Confirm the dark theme + polished metric cards render on Home, Review, History, and
    Settings, and that editable text areas are no longer forced to monospace while
    `code`/paths still are.
12. `docker-compose build` and confirm `.streamlit/config.toml` is present in the image so
    the theme applies in deployment.
