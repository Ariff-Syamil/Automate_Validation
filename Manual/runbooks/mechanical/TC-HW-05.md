# TC-HW-05 — Payload Handling

**Component:** Hardware &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-266
**Run immediately after:** `TC-HW-01`, `TC-HW-02` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** TC-HW-01 and TC-HW-02 passed; rated payload fixture is secured and weighed.

1. Attach the rated payload fixture to the gripper or end effector.
2. Command a controlled lift from the pickup position to the validation hold position.
3. Hold the payload for the specified dwell period while monitoring joint current and position drift.
4. Lower the payload back to the fixture and verify release without uncontrolled motion.

**Record as PASS if:** Payload lifts and lowers under control, remains stable during dwell, and shows no excessive current, strain, or position drift.
**Record as FAIL if:** Arm cannot lift the payload, drifts during dwell, trips current limits, vibrates excessively, or releases the load unsafely.
**If it fails:** Stop load testing and inspect torque limits, payload rating, joint current traces, and mechanical mounting.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-HW-05
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/mechanical/TC-HW-05.md.'
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
