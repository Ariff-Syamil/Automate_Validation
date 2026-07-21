# TC-HW-09 — Collision Detection

**Component:** Hardware &nbsp;·&nbsp; **Priority:** P1 &nbsp;·&nbsp; **Severity:** Major &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-266
**Run immediately after:** `TC-HW-01`, `TC-HW-02`, `TC-HW-03`, `TC-HW-07` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Precondition:** TC-HW-01, TC-HW-02, TC-HW-03, and TC-HW-07 passed; compliant obstacle fixture is installed.

1. Command movement along the validated collision-detection path.
2. Introduce the compliant obstacle fixture at the documented point in the path.
3. Observe detection timing, stop or retract behavior, and force/current response.
4. Remove the obstacle and verify the system requires an operator-approved recovery before continuing.

**Record as PASS if:** Collision is detected within the configured threshold, motion stops or retracts safely, and recovery requires documented operator action.
**Record as FAIL if:** Obstacle is not detected, excessive force is applied, motion continues into the obstacle, or recovery resumes without acknowledgement.
**If it fails:** Inspect collision thresholds, current sensing, and obstacle placement before repeating the case.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-HW-09
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/mechanical/TC-HW-09.md.'
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
