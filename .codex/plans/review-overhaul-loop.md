# Review Overhaul Coordinator Plan

Date: 2026-06-16

## Goal

Implement `docs/review-overhaul-and-visual-polish-plan.md` in two stages, using local fixture data and browser verification before calling the work complete.

## Source Scope

- Stage 1: Review Queue overhaul, minimal HTML-safe style helpers, fixture seeding script, escaping tests, version bump to `0.3.0`.
- Stage 2: Streamlit dark theme config, restrained visual polish in shared CSS, Dockerfile copy support for `.streamlit/`.
- Out of scope: OCR behavior, production Unraid DB changes, deployment changes, extra UX features beyond the approved plan.

## Stage 1 Steps

- [x] Write `tests/test_review_helpers.py` for `status_badge_html()` and `metadata_panel()` escaping.
- [x] Run `pytest tests/test_review_helpers.py` and confirm the new tests fail for the expected missing/unsafe helper behavior.
- [x] Patch `app/styles.py` with minimal escaped `status_badge_html()` and `metadata_panel()` helpers.
- [x] Run `pytest tests/test_review_helpers.py` and confirm the helper tests pass.
- [x] Add `scripts/seed_review_note.py` using local DB only and recursive `Path("data/png_cache").rglob("*.png")` fixture PNG lookup.
- [x] Patch `app/pages/2_Review.py` for queue position, Prev/Next navigation, confirmation reset on note change, real extraction metadata, Edit/Preview tabs, full-size image expander, and Approve & Next.
- [x] Bump `app/__init__.py` from `0.2.0` to `0.3.0`.
- [x] Re-run focused tests and seed fixture with `python -m scripts.seed_review_note`.
- [x] Launch Streamlit locally and verify Home plus Review Queue in a real browser.
- [x] Ask the read-only UX Review Agent to inspect the seeded Review flow and report blockers, important issues, and polish.
- [x] Fix accepted blocker or important UX issues, then repeat tests and browser checks until Stage 1 passes.

## Stage 2 Steps

- [x] Create `.streamlit/config.toml` with the approved dark theme.
- [x] Refine `app/styles.py` CSS for scoped monospace, metric cards, button hover states, and typography.
- [x] Update `Dockerfile` to copy `.streamlit/` into the image.
- [x] Browser-check Home, Review, History, and Settings for obvious layout/theme regressions.
- [x] Run practical tests/build checks; Docker build was skipped because the Docker engine was not running.
- [x] Complete direct browser visual pass for Home, Review, History, and Settings, with no blocker or important issues remaining.

## Verification Commands

- `pytest tests/test_review_helpers.py`
- `python -m scripts.seed_review_note`
- `streamlit run app/Home.py`
- Browser target: `http://localhost:8501`

## Safety Notes

- Do not point fixture seeding or Review-flow destructive checks at the Unraid production DB.
- Browser flow can mutate local queue state; reseed before repeated checks.
- Keep PowerShell command conventions in this repo.
