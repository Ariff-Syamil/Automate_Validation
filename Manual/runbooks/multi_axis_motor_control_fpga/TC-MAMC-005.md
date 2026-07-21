# TC-MAMC-005 — MAMC Telemetry Readback

**Component:** Telemetry Path &nbsp;·&nbsp; **Priority:** P1 &nbsp;·&nbsp; **Severity:** Major &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-237
**Run immediately after:** `TC-MAMC-001`, `TC-MAMC-002` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Precondition:** Telemetry transport is connected; command source and host logger are synchronized to the same test run.

1. Send a sequence of representative commands to each axis.
2. Capture telemetry frames or status registers after every command.
3. Compare reported mode, setpoint, feedback, enable state, and fault fields against expected values.
4. Inject a rejected command and verify telemetry reports the error without stale data.

**Record as PASS if:** Telemetry reflects the latest accepted command and measured feedback for each axis, reports faults/errors coherently, and does not expose stale or cross-axis data.
**Record as FAIL if:** Telemetry fields mismatch command state, feedback is stale, axis data is swapped, fault fields are missing, or rejected commands corrupt telemetry.
**If it fails:** Inspect telemetry packing, axis indexing, register snapshot timing, and host parser alignment.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-MAMC-005
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/multi_axis_motor_control_fpga/TC-MAMC-005.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-237
```

## Path to Automation

Current state: `automation_readiness` Automatable, `automation_status` In Progress.

**Open Questions:**

1. Does a draft pytest already exist for Telemetry Path (check `tests/` and this case's `observations` field), and if so, what's failing or missing to make it pass reliably in CI?
2. What mock/fixture data does this case need (sample frames, config files, golden vectors) that isn't committed yet?
3. Does it depend on real hardware state at all, or can it run fully headless in CI once the fixture/mocks exist?

**Implementation steps once answered:**

1. Add or finish the pytest module under the matching `tests/test_suite_*/` folder, following the structure of an existing passing suite in the same area.
2. Commit any missing fixture data referenced by the test.
3. Run `pytest` locally, confirm it's green, then flip `automation_status` to `Ready`.
