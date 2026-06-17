# Supernote Converter UX/UI Improvement Notes

Date: 2026-06-16

## Goal

Document practical UX/UI improvements for Supernote Converter without changing app behavior yet.

## Evidence Checked

- `app/Home.py` is a simple dashboard with status metrics, quick actions, recent activity, and system information.
- `app/pages/1_Scan.py` already follows a scan, select, process flow.
- `app/pages/2_Review.py` is the core review workspace, showing the original image beside editable OCR text.
- `app/pages/3_History.py` provides search, filtering, note selection, recovery actions, editing, and markdown preview.
- `app/pages/4_Settings.py` exposes OCR, path, threshold, automation, and advanced configuration.
- `app/styles.py` currently adds limited shared styling, mostly metric cards, monospace technical fields, and status colors.

## Recommended Order

1. Make the dashboard recommend the next useful action.
2. Polish the Review page as the primary daily workspace.
3. Improve Scan page queue clarity and reprocessing labels.
4. Make History easier to filter, inspect, and recover from.
5. Reorganize Settings into safer, more user-facing sections.
6. Consolidate shared status badges, empty states, and visual language.

## Notes

This is a documentation pass only. Any implementation should use a focused plan and avoid adding new workflow features unless the user approves them first.
