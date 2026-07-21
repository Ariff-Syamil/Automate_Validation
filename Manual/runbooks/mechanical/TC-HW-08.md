# TC-HW-08 — Emergency Stop

**Component:** Hardware &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-266
**Run immediately after:** `TC-HW-01`, `TC-HW-02`, `TC-HW-03`, `TC-HW-07` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** TC-HW-01, TC-HW-02, TC-HW-03, and TC-HW-07 passed; emergency stop circuit has been pre-checked.

1. Command a slow controlled movement along a safe path.
2. Trigger the emergency stop while motion is active.
3. Verify all motion commands are inhibited immediately and motor power enters the configured safe state.
4. Attempt a normal movement command before reset and confirm it is rejected.
5. Reset the emergency stop and confirm the controller requires the documented recovery sequence.

**Record as PASS if:** Emergency stop halts motion immediately, prevents further movement until reset, and leaves the system in the documented safe state.
**Record as FAIL if:** Stop response is delayed, any joint continues moving, movement commands are accepted before reset, or recovery bypasses safety interlocks.
**If it fails:** Keep the system disabled and inspect E-stop wiring, safety relay status, and controller interlock handling.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-HW-08
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/mechanical/TC-HW-08.md.'
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
