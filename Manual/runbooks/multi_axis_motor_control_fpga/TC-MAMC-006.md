# TC-MAMC-006 — MAMC Multi-Axis Soak

**Component:** Multi-Axis Soak &nbsp;·&nbsp; **Priority:** P1 &nbsp;·&nbsp; **Severity:** Major &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-237
**Run immediately after:** `TC-MAMC-003`, `TC-MAMC-004`, `TC-MAMC-005` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Precondition:** PWM/current-loop, fault interlock, and telemetry cases passed; thermal/current logging is enabled for all axes.

1. Enable all supported axes with safe validation loads.
2. Run the coordinated multi-axis command profile for the specified cycle count or duration.
3. Log current, temperature, command state, feedback, and fault telemetry for every axis.
4. Verify no axis starves, drifts, or misses command updates during the run.
5. Stop the profile and verify all axes enter the documented safe state.

**Record as PASS if:** All axes complete the soak profile without unexpected faults, telemetry gaps, thermal/current violations, command starvation, or unsafe shutdown behavior.
**Record as FAIL if:** Any axis faults unexpectedly, telemetry drops, current/temperature exceeds limit, command updates starve, drift exceeds tolerance, or safe shutdown fails.
**If it fails:** Correlate axis telemetry, current/thermal logs, and command scheduler traces to identify the first failing axis or shared resource.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-MAMC-006
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/multi_axis_motor_control_fpga/TC-MAMC-006.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-237
```

## Path to Automation

Current state: `automation_readiness` Semi-Automatable, `automation_status` In Progress.

**Open Questions:**

1. Which parts of Multi-Axis Soak can already be driven by a scriptable API/SDK/CLI, and which genuinely need a human at the bench (physical setup, visual/audible judgement)?
2. What's today's pass/fail signal, and is there a sensor/log/counter equivalent that could replace the human observation?
3. Is there a safe way to simulate or mock the hardware response for a CI-only smoke check, even if the full HIL case still needs a human?

**Implementation steps once answered:**

1. Script whatever is answered "yes" to the scriptable-parts question above into a HIL test module (see `tests/test_suite_hil/testcase_hil_gates.py` for the pattern).
2. Keep a required manual sign-off step for whatever remains human-only, especially where `severity` is `Critical`.
3. Run once for real, record the result, and flip `automation_status` to `Ready` only for the parts that are genuinely automated (or keep it `Semi-Automatable` permanently if a human step will always remain).
