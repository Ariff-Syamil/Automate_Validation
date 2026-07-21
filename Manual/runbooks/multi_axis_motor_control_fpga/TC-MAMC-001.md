# TC-MAMC-001 — MAMC FPGA Bring-Up

**Component:** MAMC FPGA Bring-Up &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-237
**Run immediately after:** `TC-SW-002` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** MAMC FPGA bitstream is built; CAN-FD command format is available; bench power supply and safe dummy load are connected.

1. Program the MAMC FPGA bitstream onto the target board.
2. Release reset and verify all clocks and reset-done indicators.
3. Read the control/status register block through the configured host interface.
4. Verify firmware or register version, axis count, and fault status fields.
5. Assert the design powers up with all axes disabled and no latched faults.

**Record as PASS if:** FPGA programs successfully, register reads return expected version/axis metadata, all axes are disabled at boot, and no unexpected faults are latched.
**Record as FAIL if:** Bitstream does not program, clocks do not lock, register access fails, axis metadata is wrong, or any unexpected fault is latched at boot.
**If it fails:** Check bitstream version, clock/reset tree, host-interface wiring, and power sequencing before running axis tests.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-MAMC-001
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/multi_axis_motor_control_fpga/TC-MAMC-001.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-237
```

## Path to Automation

Current state: `automation_readiness` Semi-Automatable, `automation_status` In Progress.

**Open Questions:**

1. Which parts of MAMC FPGA Bring-Up can already be driven by a scriptable API/SDK/CLI, and which genuinely need a human at the bench (physical setup, visual/audible judgement)?
2. What's today's pass/fail signal, and is there a sensor/log/counter equivalent that could replace the human observation?
3. Is there a safe way to simulate or mock the hardware response for a CI-only smoke check, even if the full HIL case still needs a human?

**Implementation steps once answered:**

1. Script whatever is answered "yes" to the scriptable-parts question above into a HIL test module (see `tests/test_suite_hil/testcase_hil_gates.py` for the pattern).
2. Keep a required manual sign-off step for whatever remains human-only, especially where `severity` is `Critical`.
3. Run once for real, record the result, and flip `automation_status` to `Ready` only for the parts that are genuinely automated (or keep it `Semi-Automatable` permanently if a human step will always remain).
