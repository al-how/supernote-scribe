# Supernote Converter Improvement Notes

Date: 2026-06-15

## Goal

Capture a small, practical backlog of improvements for Supernote Converter without adding features or changing behavior yet.

## Evidence Checked

- `pytest --tb=short -q --basetemp=pytest-temp` passed with 81 tests.
- Plain `pytest` failed in this Windows session because pytest could not write to the default temp/cache paths.
- `.github/workflows/docker-publish.yml` currently builds and pushes the Docker image but does not run tests first.
- `start.sh` runs the webhook server in the background and Streamlit in the foreground.
- `app/webhook.py` can start a background processor for each `/process` request.
- Largest maintenance surfaces are `app/database.py` and `app/services/processor.py`.

## Recommended Order

1. Make the local test command reliable on Windows.
2. Add CI tests before Docker image publishing.
3. Clean up branch/push state before more work accumulates.
4. Add a webhook/process concurrency guard.
5. Improve operational status and health reporting.
6. Revisit container process supervision.
7. Split large files only when doing related maintenance.
8. Clarify `.gitignore` treatment of tests and generated artifacts.

## Notes

This is a planning/documentation pass only. Any implementation should get a focused plan first, with the smallest useful slice preferred.
