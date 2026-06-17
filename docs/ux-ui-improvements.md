# UX/UI Improvement Backlog

Supernote Converter is already functional and deployed. The best user experience improvements are not a broad redesign; they are targeted polish around the daily workflow: seeing what needs attention, scanning safely, reviewing OCR output quickly, and recovering when something goes wrong.

This document is a proposal backlog only. It does not commit the project to new features or behavior changes.

## 1. Make the Dashboard Action-Oriented

Current state:

- The Home page shows pending, review, and processed counts.
- It provides quick links to Scan, Review, and History.
- Recent activity appears as a short log list.
- System information is available in an expander.

Recommended improvement:

- Show one clear recommended next action, based on current status:
  - `Review notes` when review items exist.
  - `Process pending notes` when the queue has pending items.
  - `Scan for new notes` when there is nothing waiting.
- Add a compact operational strip for source path, output path, OCR provider, and last activity.
- Group recent activity by outcome where possible, such as success, review, and error.
- Keep detailed system configuration tucked away unless it needs attention.

Why it matters:

The dashboard should answer, "What should I do now?" rather than only reporting counts.

## 2. Make Scan and Process Feel More Guided

Current state:

- The Scan page has three numbered sections: scan, select, process.
- Discovered notes are shown in an editable table.
- Pending notes can be processed, and long processing runs show progress and logs.
- Reprocessing is supported, but the consequences are not especially visible before action.

Recommended improvement:

- Add a compact workflow indicator: `Scan -> Select -> Process -> Review`.
- Group discovered notes by folder and status so batches are easier to understand.
- Use clearer labels for processing state:
  - `New`
  - `Pending`
  - `Already processed`
  - `Will reprocess`
  - `Needs review`
- Make selected count more prominent near the process button.
- Replace the pending list expander with a queue summary and optional details.
- Make abort state visually distinct from normal warnings.

Why it matters:

Scanning and reprocessing are powerful actions. The page should make it obvious what will happen before the user starts a run.

## 3. Polish Review as the Primary Workspace

Current state:

- The Review page shows the original image beside editable extracted text.
- Multi-page notes use tabs.
- Actions include approve, save draft, rescan, and reject.
- The note selector lives in the sidebar.
- The UI currently displays `Confidence: N/A`.

Recommended improvement:

- Treat Review as the core workspace and give it the most polish.
- Keep the primary actions visible in a sticky action area:
  - `Approve & Save`
  - `Save Draft`
  - `Rescan`
  - `Reject`
- Remove or replace `Confidence: N/A` until real confidence/provenance data exists.
- Show useful page context, such as `Page 2 of 5`.
- Improve missing-image states with a clear explanation and next action.
- Preserve the side-by-side image/text layout, since it matches the review task well.
- Make destructive or expensive actions feel deliberate without slowing down normal approval.

Why it matters:

Review is where the app earns trust. The user needs to compare handwriting and text quickly, make light edits, and approve without losing their place.

## 4. Improve History as a Search and Recovery Tool

Current state:

- History supports filename search, status filtering, and a result limit.
- Selecting a row opens metadata, preview, edit, move-to-review, and rescan actions.
- Status colors are applied through shared styling.

Recommended improvement:

- Add quick filter presets:
  - `Approved`
  - `Auto-approved`
  - `Needs review`
  - `Errors`
  - `Rejected`
- Make the selected-note detail area feel like a clear inspector below the table.
- Use consistent status badges instead of relying only on dataframe styling.
- Highlight missing output files and errored notes more clearly.
- Rename actions around user intent:
  - `Edit markdown`
  - `Send back to review`
  - `Run OCR again`
- Keep recovery actions available, but separate them from normal browsing.

Why it matters:

History is not just an archive. It is where the user checks whether automation worked and fixes cases that slipped through.

## 5. Make Settings Safer and Friendlier

Current state:

- Settings exposes provider, endpoint, OpenAI fallback, thresholds, paths, automation, and advanced reset controls.
- Connection tests exist for OCR providers and paths.
- Some settings are implementation-facing, including a currently unused quality threshold.

Recommended improvement:

- Organize settings into user-facing sections:
  - `Folders`
  - `OCR`
  - `Automation`
  - `Advanced`
- Show connection status badges near provider and path fields.
- Hide unused or rarely changed settings behind Advanced.
- Reword technical labels where possible:
  - `Where Supernote files are read from`
  - `Where markdown files are saved`
  - `Local OCR provider`
- Make reset-to-defaults visually separate from ordinary save actions.
- Replace celebratory animations on save with a quieter confirmation.

Why it matters:

Settings should help a non-coder operator confirm the app is wired correctly without making routine configuration feel risky.

## 6. Consolidate Visual Language

Current state:

- Shared CSS exists, but most pages are still close to Streamlit defaults.
- Status colors are centralized.
- Emoji labels are used heavily and inconsistently.

Recommended improvement:

- Create shared UI helpers for:
  - status badges
  - empty states
  - action rows
  - path/config summaries
  - warning and error callouts
- Use a calmer document-workbench style:
  - readable spacing
  - restrained borders
  - consistent action placement
  - monospace only for paths, logs, code, and model names
- Reduce decorative emoji where icons or plain labels would be clearer.
- Keep the interface dense enough for repeated use, rather than turning it into a marketing-style page.

Why it matters:

Consistent visual treatment makes the app easier to scan and lowers the chance of misreading state during a batch run.

## Suggested First Slice

The smallest high-value UX bundle is:

1. Dashboard: show the single recommended next action.
2. Review: polish the action area and remove confusing placeholder confidence text.
3. History: add clearer filters and consistent status badges.
4. Settings: group fields into friendlier sections and move advanced controls out of the normal path.

This improves the daily experience without changing OCR logic, database behavior, deployment, or automation.
