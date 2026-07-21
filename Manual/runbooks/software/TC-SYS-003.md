# TC-SYS-003 — Observation Action Contract

**Component:** Control Loop Contract &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-235
**Also depends on (covered in Phase 1, already automated):** `TC-SW-007`, `TC-SW-010`

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** Automate5 source checkout and declared test dependencies available.

1. Build synthetic observation
2. Send through fake ZMQ REQ/REP service
3. Return synthetic action chunk
4. Validate action shape and convert command to packet
5. Exercise timeout and invalid-action errors

**Record as PASS if:** Contract validates schemas, converts commands, and reports coded errors.
**Record as FAIL if:** Unexpected exception, mismatch, missing artifact, or unsafe response.
**If it fails:** Inspect the referenced Automate5 module, fixture, and pytest output.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-SYS-003
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/software/TC-SYS-003.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-235
```

## Path to Automation

Current state: `automation_readiness` Automatable, `automation_status` In Progress.

**Open Questions:**

1. Does a draft pytest already exist for Control Loop Contract (check `tests/` and this case's `observations` field), and if so, what's failing or missing to make it pass reliably in CI?
2. What mock/fixture data does this case need (sample frames, config files, golden vectors) that isn't committed yet?
3. Does it depend on real hardware state at all, or can it run fully headless in CI once the fixture/mocks exist?

**Implementation steps once answered:**

1. Add or finish the pytest module under the matching `tests/test_suite_*/` folder, following the structure of an existing passing suite in the same area.
2. Commit any missing fixture data referenced by the test.
3. Run `pytest` locally, confirm it's green, then flip `automation_status` to `Ready`.
