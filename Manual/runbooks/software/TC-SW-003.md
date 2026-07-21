# TC-SW-003 — EtherCAT PDO Cycle

**Component:** EtherCAT Stack &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-197
**Run immediately after:** `TC-FPGA-003`, `TC-FPGA-004`, `TC-FPGA-005`, `TC-SW-001` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** EtherCAT master runtime is installed; FPGA Ethernet path and UDP packet exchange dependencies have passed; target slave is reachable.

1. Start the EtherCAT master runtime with the target network interface selected.
2. Discover the expected slave device and confirm it reaches the operational state.
3. Run cyclic PDO exchange for the configured validation duration.
4. Record cycle time, jitter, missed frames, and process-data values.
5. Stop the master cleanly and confirm the slave returns to a safe state.

**Record as PASS if:** Expected slave is discovered, reaches operational state, exchanges PDO data cyclically within jitter tolerance, and shuts down cleanly.
**Record as FAIL if:** Slave is not discovered, state transition fails, PDO values mismatch, jitter exceeds tolerance, frames are missed, or shutdown leaves an unsafe state.
**If it fails:** Inspect EtherCAT state machine transitions, distributed-clock sync, NIC binding, and slave diagnostics.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-SW-003
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/software/TC-SW-003.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-197
```

## Path to Automation

Current state: `automation_readiness` Semi-Automatable, `automation_status` In Progress.

**Open Questions:**

1. Which parts of EtherCAT Stack can already be driven by a scriptable API/SDK/CLI, and which genuinely need a human at the bench (physical setup, visual/audible judgement)?
2. What's today's pass/fail signal, and is there a sensor/log/counter equivalent that could replace the human observation?
3. Is there a safe way to simulate or mock the hardware response for a CI-only smoke check, even if the full HIL case still needs a human?

**Implementation steps once answered:**

1. Script whatever is answered "yes" to the scriptable-parts question above into a HIL test module (see `tests/test_suite_hil/testcase_hil_gates.py` for the pattern).
2. Keep a required manual sign-off step for whatever remains human-only, especially where `severity` is `Critical`.
3. Run once for real, record the result, and flip `automation_status` to `Ready` only for the parts that are genuinely automated (or keep it `Semi-Automatable` permanently if a human step will always remain).
