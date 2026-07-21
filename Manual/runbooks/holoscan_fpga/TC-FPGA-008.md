# TC-FPGA-008 — Camera Module I2C Bus-Scan Regression

**Component:** MIPI Camera Input (Fault Detection) &nbsp;·&nbsp; **Priority:** P1 &nbsp;·&nbsp; **Severity:** Major &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-229
**Also depends on (covered in Phase 1, already automated):** `TC-FPGA-001`

## Manual Procedure

**Precondition:** Camera module under test connected to a validated AvantX camera slot.

1. Connect the camera module under test to a known-good AvantX camera slot.
2. Run an I2C bus-id scan against the expected camera address.
3. Confirm the camera responds and reports its expected device ID.
4. Repeat on the second camera slot to rule out slot-specific faults.
5. Record pass/fail per camera unit serial number for traceability.

**Record as PASS if:** Camera responds to the I2C bus-id scan with the correct device ID on both camera slots.
**Record as FAIL if:** I2C scan times out, wrong device ID is returned, or camera fails on one slot but not the other (indicating a module-specific hardware fault).
**If it fails:** Quarantine the camera unit, request a replacement from the CH team, and log the failing serial number.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-FPGA-008
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/holoscan_fpga/TC-FPGA-008.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-229
```
