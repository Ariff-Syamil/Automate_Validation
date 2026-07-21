# TC-HW-10 — Continuous Operation

**Component:** Hardware &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-266
**Run immediately after:** `TC-HW-01`, `TC-HW-02`, `TC-HW-03`, `TC-HW-07` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** TC-HW-01, TC-HW-02, TC-HW-03, and TC-HW-07 passed; thermal/current logging is enabled.

1. Load the repeated-cycle validation program with representative movement and dwell phases.
2. Run the cycle for the specified duration or cycle count while logging temperatures, currents, and controller faults.
3. Check for drift, missed steps, abnormal noise, and thermal rise at regular intervals.
4. Stop the cycle and verify the arm returns to a safe parked state.

**Record as PASS if:** The arm completes the full duration or cycle count without overheating, controller faults, position drift, or abnormal mechanical behavior.
**Record as FAIL if:** Any over-temperature condition, repeated controller fault, position drift, missed motion, abnormal noise, or unsafe shutdown occurs.
**If it fails:** Collect thermal/current logs and inspect mechanical wear or controller fault history before retrying.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-HW-10
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/mechanical/TC-HW-10.md.'
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
