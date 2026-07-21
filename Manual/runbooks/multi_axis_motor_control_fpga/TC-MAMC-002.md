# TC-MAMC-002 — MAMC Command Decode

**Component:** Command Decoder &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-237
**Run immediately after:** `TC-MAMC-001`, `TC-SW-002` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** TC-MAMC-001 passed; host can send representative CAN-FD or register-mapped motor commands.

1. Send valid speed, position, torque, reset, and estop command frames for each supported axis.
2. Read decoded command fields from debug/status registers or telemetry output.
3. Send malformed frames covering bad axis ID, invalid mode, out-of-range setpoint, and wrong payload length.
4. Verify malformed commands are rejected without changing active command state.

**Record as PASS if:** Valid commands decode to the expected axis, mode, and setpoint values; malformed commands are rejected and reported without changing active state.
**Record as FAIL if:** A valid command decodes incorrectly, malformed input is accepted, active state changes after a rejected command, or error reporting is missing.
**If it fails:** Inspect frame parsing, axis bounds checks, payload length validation, and command-state update ordering.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-MAMC-002
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/multi_axis_motor_control_fpga/TC-MAMC-002.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-237
```

## Path to Automation

Current state: `automation_readiness` Automatable, `automation_status` In Progress.

**Open Questions:**

1. Does a draft pytest already exist for Command Decoder (check `tests/` and this case's `observations` field), and if so, what's failing or missing to make it pass reliably in CI?
2. What mock/fixture data does this case need (sample frames, config files, golden vectors) that isn't committed yet?
3. Does it depend on real hardware state at all, or can it run fully headless in CI once the fixture/mocks exist?

**Implementation steps once answered:**

1. Add or finish the pytest module under the matching `tests/test_suite_*/` folder, following the structure of an existing passing suite in the same area.
2. Commit any missing fixture data referenced by the test.
3. Run `pytest` locally, confirm it's green, then flip `automation_status` to `Ready`.
