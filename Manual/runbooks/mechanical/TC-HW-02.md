# TC-HW-02 — Single Joint Movement

**Component:** Hardware &nbsp;·&nbsp; **Priority:** P1 &nbsp;·&nbsp; **Severity:** Major &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-266
**Run immediately after:** `TC-HW-01` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Precondition:** TC-HW-01 passed; arm is homed; joint angle limits are configured.

1. Select one joint at a time: shoulder, elbow, then wrist.
2. Command each joint through low-speed positive and negative movement within its safe range.
3. Repeat the movement at nominal validation speed.
4. Observe encoder feedback, limit enforcement, vibration, and audible noise for each joint.

**Record as PASS if:** Each joint moves smoothly in both directions, follows commanded speed, stops within configured limits, and reports stable encoder feedback without abnormal noise.
**Record as FAIL if:** Any joint stalls, moves in the wrong direction, exceeds configured limits, oscillates, or reports unstable encoder feedback.
**If it fails:** Disable the affected joint and inspect motor driver status, encoder calibration, and configured soft limits.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-HW-02
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/mechanical/TC-HW-02.md.'
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
