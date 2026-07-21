# TC-SW-002 — CAN-FD Frame Round Trip

**Component:** CAN-FD Protocol &nbsp;·&nbsp; **Priority:** P1 &nbsp;·&nbsp; **Severity:** Major &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-237
**Dependency:** None.

## Manual Procedure

**Precondition:** CAN-FD encode/decode library is installed; representative DBC or frame definition is available for validation.

1. Build representative CAN-FD frames covering nominal motor command, boundary payload length, and invalid field cases.
2. Encode each frame using the software protocol helper.
3. Transmit or loop back the encoded frame through the available CAN-FD validation path.
4. Decode the received bytes and compare identifier, DLC, flags, and payload fields.
5. Verify invalid frames are rejected with a clear error.

**Record as PASS if:** Valid frames round-trip with matching identifier, DLC, flags, and payload values; invalid frames fail deterministically without corrupting state.
**Record as FAIL if:** Frame fields mismatch after decode, invalid data is accepted, payload length is wrong, or transmission rejects a valid frame.
**If it fails:** Validate bit timing, DBC/frame definitions, endian handling, and encode/decode boundary checks.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-SW-002
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/software/TC-SW-002.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-237
```

## Path to Automation

Current state: `automation_readiness` Automatable, `automation_status` In Progress.

**Open Questions:**

1. Does a draft pytest already exist for CAN-FD Protocol (check `tests/` and this case's `observations` field), and if so, what's failing or missing to make it pass reliably in CI?
2. What mock/fixture data does this case need (sample frames, config files, golden vectors) that isn't committed yet?
3. Does it depend on real hardware state at all, or can it run fully headless in CI once the fixture/mocks exist?

**Implementation steps once answered:**

1. Add or finish the pytest module under the matching `tests/test_suite_*/` folder, following the structure of an existing passing suite in the same area.
2. Commit any missing fixture data referenced by the test.
3. Run `pytest` locally, confirm it's green, then flip `automation_status` to `Ready`.
