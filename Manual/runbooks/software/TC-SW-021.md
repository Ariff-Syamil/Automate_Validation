# TC-SW-021 — Gesture Worker Signals

**Component:** Gesture Controller &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-220
**Dependency:** None.

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** Automate5 source checkout and declared test dependencies available.

1. Monkeypatch GestureWorker with fake worker
2. Call start_recognition twice
3. Emit fake gesture, speed, stop, bbox, frame, and error signals
4. Verify forwarding, error propagation, stop, and reset cleanup

**Record as PASS if:** Start/stop is idempotent, signals are forwarded, and cleanup is deterministic.
**Record as FAIL if:** Unexpected exception, mismatch, missing artifact, or unsafe response.
**If it fails:** Inspect the referenced Automate5 module, fixture, and pytest output.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-SW-021
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/software/TC-SW-021.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-220
```

## Path to Automation

Current state: `automation_readiness` Automatable, `automation_status` In Progress.

**Open Questions:**

1. Does a draft pytest already exist for Gesture Controller (check `tests/` and this case's `observations` field), and if so, what's failing or missing to make it pass reliably in CI?
2. What mock/fixture data does this case need (sample frames, config files, golden vectors) that isn't committed yet?
3. Does it depend on real hardware state at all, or can it run fully headless in CI once the fixture/mocks exist?

**Implementation steps once answered:**

1. Add or finish the pytest module under the matching `tests/test_suite_*/` folder, following the structure of an existing passing suite in the same area.
2. Commit any missing fixture data referenced by the test.
3. Run `pytest` locally, confirm it's green, then flip `automation_status` to `Ready`.
