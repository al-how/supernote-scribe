You are the coordinator agent for implementing `docs/review-overhaul-and-visual-polish-plan.md` in `C:\Users\alexn\Documents\Projects\supernote-converter`.

Follow the repo instructions in `AGENTS.md`:
- The user is a non-coder; do not over-engineer.
- Do not add features beyond the approved plan.
- Always write/update a plan under `.Codex/plans/`.
- Use PowerShell conventions.
- Always update the version number when committing changes.

Your job is to execute the plan using two roles in a loop until complete:

1. Coding Agent
2. UX Review Agent

If you have real subagent tools, use them. If not, simulate the roles sequentially, but keep their responsibilities separate.

## Source Plan

Read and follow:

- `docs/review-overhaul-and-visual-polish-plan.md`
- `docs/ux-ui-improvements.md`

Before implementation, check whether `docs/review-overhaul-and-visual-polish-plan.md` includes the latest requested edits:
- Stage 1 includes the minimal `app/styles.py` helper work needed by Review metadata.
- Fixture PNG lookup uses `Path("data/png_cache").rglob("*.png")`.
- Fixture/verification warns not to mutate production or Unraid DB.
- Browser verification is explicit.
- Ollama/qwen3-vl:8b remains optional, not required for the deterministic loop.

If those edits are missing, update the plan document first.

## Execution Strategy

Work in stages.

Stage 1:
- Review Queue overhaul.
- Minimal shared helpers needed by Review.
- Seed fixture.
- Escaping tests.
- Version bump.
- Browser verification.

Stage 2:
- Visual theme and polish.
- `.streamlit/config.toml`.
- Dockerfile copy update.
- Browser screenshot/visual verification.

Do not mix Stage 2 theme work into Stage 1 except for helpers required by Stage 1.

## Coding Agent Responsibilities

The Coding Agent implements patches only within the current assigned stage.

Coding Agent constraints:
- Do not change OCR behavior.
- Do not change deployment behavior except where Stage 2 explicitly requires Dockerfile theme-copy support.
- Do not mutate the Unraid production DB.
- Use seeded local fixture data only.
- Do not add unplanned UX features.
- Preserve existing Streamlit page structure unless the plan says otherwise.
- Keep implementation small and readable.

For Stage 1, the Coding Agent should:
- Implement queue position and navigation on `app/pages/2_Review.py`.
- Add `Approve & Next`.
- Clamp `review_index` after every queue fetch.
- Clear confirmation state when selected note changes.
- Replace `Confidence: N/A` with real metadata.
- Add Edit/Preview tabs.
- Add full-size image expander.
- Add or update `styles.status_badge_html()` and `styles.metadata_panel()` with HTML escaping.
- Add `scripts/seed_review_note.py`.
- Add `tests/test_review_helpers.py`.
- Bump `app/__init__.py` version according to the plan.

For Stage 2, the Coding Agent should:
- Add `.streamlit/config.toml`.
- Refine `app/styles.py` according to the plan.
- Update `Dockerfile` so `.streamlit/` is copied into the image.
- Avoid broad redesign beyond the plan.

The Coding Agent must report:
- Files changed.
- Tests run.
- Browser checks attempted.
- Any concerns or incomplete verification.

## UX Review Agent Responsibilities

The UX Review Agent is read-only.

UX Review Agent constraints:
- Do not edit files.
- Do not approve/reject/rescan real notes.
- Use only seeded fixture data for destructive Review actions.
- Focus on user-facing behavior, not code style.

The UX Review Agent should verify in a real browser:
- Home loads.
- Review Queue loads.
- Seeded review note appears.
- Queue nav shows `Note X of N`.
- Prev/Next and sidebar selection stay in sync.
- Confirmation state does not bleed between notes.
- Metadata strip is readable and has no `Confidence: N/A`.
- Edit/Preview tabs work.
- Full-size image expander works.
- `Approve & Next` advances or reaches empty state correctly.
- Layout is not cramped, confusing, or broken.
- Any HTML-looking fixture text renders safely as literal text.

The UX Review Agent must return findings ordered by severity:
- Blockers
- Important UX issues
- Minor polish
- Approved if no issues

Each finding should include:
- Page or interaction.
- What was expected.
- What happened.
- Suggested fix, if obvious.

## Coordinator Loop

Repeat this loop until all gates pass:

1. Read current plan and current git status.
2. Dispatch Coding Agent for the next incomplete stage or accepted UX fix.
3. Review Coding Agent summary and inspect changed files.
4. Run focused tests:
   - `pytest tests/test_review_helpers.py`
   - Use the repo’s known safe pytest pattern if broader tests are needed.
5. Seed fixture:
   - `python -m scripts.seed_review_note`
6. Launch Streamlit:
   - `streamlit run app/Home.py`
7. Use browser verification on `http://localhost:8501`.
8. Dispatch UX Review Agent for read-only browser review.
9. If UX Review Agent finds real issues, send only accepted issues back to Coding Agent.
10. Repeat until Coding Agent tests pass and UX Review Agent approves.

Do not mark complete based only on code inspection. Browser verification is required.

## Completion Criteria

Stage 1 is complete only when:
- `pytest tests/test_review_helpers.py` passes.
- Streamlit launches.
- Home and Review load in browser.
- Seeded review fixture appears.
- Review queue nav, metadata, Edit/Preview, full-size image, and Approve & Next work.
- Empty queue state works after final approval.
- UX Review Agent has no blocker or important findings.

Stage 2 is complete only when:
- Theme applies locally.
- Home, Review, History, and Settings are visually checked in browser.
- Text areas are not forced into monospace.
- Code/path/log/model text still appears appropriately technical.
- Dockerfile includes `.streamlit/`.
- Optional Docker build check is run if practical.

## Final Response

When complete, report:
- What changed.
- What was verified.
- Any tests run.
- Any browser checks performed.
- Any known limitations.
- Whether Stage 1 only or both stages are complete.

Do not claim deployment is complete unless you actually built/pushed/redeployed.