# TC-HW-07 — Position Accuracy

**Component:** Hardware &nbsp;·&nbsp; **Priority:** P1 &nbsp;·&nbsp; **Severity:** Major &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-266
**Run immediately after:** `TC-HW-01`, `TC-HW-02`, `TC-HW-03` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Precondition:** TC-HW-01, TC-HW-02, and TC-HW-03 passed; measurement fixture or calibrated reference is available.

1. Command the arm to the first predefined coordinate and wait for settled state.
2. Measure end-effector position using the calibrated reference method.
3. Repeat for at least three coordinates across the validated workspace.
4. Compare measured coordinates against commanded coordinates and record the maximum error.

**Record as PASS if:** All measured positions are within configured tolerance and no coordinate shows repeatable bias outside the acceptance band.
**Record as FAIL if:** Any measured coordinate exceeds tolerance, position repeatability is unstable, or the arm cannot settle at a commanded coordinate.
**If it fails:** Recalibrate home position, inspect kinematic parameters, and repeat the failed coordinate set.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-HW-07
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/mechanical/TC-HW-07.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-266
```

## Path to Automation

Current state: `automation_readiness` Semi-Automatable, `automation_status` In Progress.

**Open Questions:**

1. Which parts of Hardware can already be driven by a scriptable API/SDK/CLI, and which genuinely need a human at the bench (physical setup, visual/audible judgement)?
2. What's today's pass/fail signal, and is there a sensor/log/counter equivalent that could replace the human observation?
3. Is there a safe way to simulate or mock the hardware response for a CI-only smoke check, even if the full HIL case still needs a human?

**Implementation steps once answered:**

1. Script whatever is answered "yes" to the scriptable-parts question above into a HIL test module (see `tests/test_suite_hil/testcase_hil_gates.py` for the pattern).
2. Keep a required manual sign-off step for whatever remains human-only, especially where `severity` is `Critical`.
3. Run once for real, record the result, and flip `automation_status` to `Ready` only for the parts that are genuinely automated (or keep it `Semi-Automatable` permanently if a human step will always remain).
