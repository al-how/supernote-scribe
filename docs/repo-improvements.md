# Supernote Converter Improvement Backlog

This project is already functional and deployed, so the best next improvements are mostly about trust, operations, and maintenance. The goal is to make the unattended Unraid workflow easier to verify and harder to accidentally break.

## 1. Make Local Tests Reliable

Current finding:

```powershell
pytest --tb=short -q --basetemp=pytest-temp
```

passes with 81 tests. Plain `pytest` failed in this Windows session because pytest could not write to default temp/cache paths.

Recommended improvement:

- Add a repo-standard test command to docs, `pytest.ini`, or a small PowerShell helper.
- Keep the command explicit about `--basetemp=pytest-temp`.
- Consider disabling or redirecting pytest cache if `.pytest_cache` permissions remain noisy.

Why it matters:

The test suite is useful, but a default command that fails for environment reasons makes future changes feel less trustworthy than they are.

## 2. Run Tests Before Publishing Docker Images

Current finding:

`.github/workflows/docker-publish.yml` builds and pushes Docker images, but does not run the Python test suite first.

Recommended improvement:

- Add a CI test job before `build-and-push`.
- Make the Docker publish job depend on the test job.
- Use Python 3.11 to match the deployed runtime.

Why it matters:

The `latest` image should only update after the app test suite passes.

## 3. Clean Up Branch and Push State

Current finding:

The local branch state should be checked before new implementation work. In this session, `git status --short --branch` reported `master...origin/master [behind 1]`.

Recommended improvement:

- Reconcile local `master` with `origin/master`.
- Confirm whether any prior local-only commits still need pushing or whether origin has moved ahead.
- Avoid stacking new code changes until the branch state is clear.

Why it matters:

Deployment is driven by GitHub Actions and GHCR, so branch clarity directly affects what gets built and deployed.

## 4. Add Webhook Concurrency Protection

Current finding:

`POST /process` scans for notes and starts a background `python -m app --process` run. Multiple webhook calls can start multiple processors.

Recommended improvement:

- Add a simple processing lock or database-backed guard.
- Return a clear `already_running` response if a run is active.
- Clear stale locks safely if a process crashes.

Why it matters:

This protects against duplicate runs from n8n, iOS Shortcuts, retries, or repeated manual taps.

## 5. Improve Status and Health Visibility

Current finding:

`GET /status` returns pending count and recent activity. `GET /health` returns only `{"status": "ok"}`.

Recommended improvement:

- Include counts for `pending`, `processing`, `review`, and `error`.
- Include the last successful run and last error.
- Include the configured OCR provider and maybe whether the local provider is reachable.
- Consider making the Docker healthcheck validate both Streamlit and webhook health.

Why it matters:

The unattended workflow needs quick, human-readable answers to "is it working?" and "what happened last?"

## 6. Revisit Container Process Supervision

Current finding:

`start.sh` starts `uvicorn` in the background and Streamlit in the foreground. If the webhook server exits, Streamlit can keep the container alive.

Recommended improvement:

- Either supervise both processes in one container or split Streamlit and webhook into separate services.
- At minimum, improve healthchecks so webhook failure is visible.

Why it matters:

The webhook is part of the automation surface. A partially healthy container can hide the exact failure the automation depends on.

## 7. Refactor Large Files Only When Useful

Current finding:

The largest files are `app/database.py` and `app/services/processor.py`.

Recommended improvement:

- Avoid a broad refactor for its own sake.
- When touching these areas, consider small splits:
  - database schema/migrations versus query operations
  - single-note processing versus batch orchestration

Why it matters:

Smaller modules would make future changes easier, but this should stay tied to actual maintenance work.

## 8. Clarify `.gitignore` Treatment of Tests

Current finding:

`.gitignore` contains `tests/`, while this workspace has a real, passing test suite.

Recommended improvement:

- Confirm whether tests are intentionally tracked.
- If they are tracked, remove or narrow the `tests/` ignore rule.
- Add generated folders such as `pytest-temp/` if they remain part of the standard workflow.

Why it matters:

Tests should not feel accidental or easy to drop from version control.

## Suggested First Slice

The smallest high-value bundle is:

1. Make the local test command reliable.
2. Add CI tests before Docker publish.
3. Add a webhook `already_running` guard.

That gives the project better safety without changing the user-facing workflow.
