Task 4 review fix plan

1. Add a regression test proving a public notification call returns before a slow Pushover HTTP send completes.
2. Make enabled notification sends dispatch HTTP work on a daemon background thread while preserving disabled-toggle return behavior and warning logs.
3. If scheduler double-scan is small, change the scheduled wake to skip a second scan and cover it with a focused test.
4. Run focused Task 4 tests, then the full pytest command if feasible.
5. Append the fix report to `.superpowers/sdd/task-4-report.md`.
