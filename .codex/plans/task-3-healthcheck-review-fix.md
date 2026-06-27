# Task 3 Healthcheck Review Fix Plan

1. Add a focused regression test proving `GET /health` returns a non-2xx response when the worker database/runtime check fails.
2. Run the focused test and confirm it fails for the expected reason.
3. Change the worker health endpoint to return/raise HTTP 503 for unhealthy runtime state while preserving the JSON body.
4. Update the README endpoint section from stale webhook wording to current worker endpoint shapes.
5. Run focused Task 3 tests, then the full pytest suite if feasible.
6. Append a concise fix report to `.superpowers/sdd/task-3-report.md`.
