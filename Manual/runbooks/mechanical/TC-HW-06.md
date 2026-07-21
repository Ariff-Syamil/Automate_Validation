# TC-HW-06 — Speed Control

**Component:** Hardware &nbsp;·&nbsp; **Priority:** P1 &nbsp;·&nbsp; **Severity:** Major &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-266
**Run immediately after:** `TC-HW-01` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Precondition:** TC-HW-01 passed; speed profiles for low, medium, and high validation modes are configured.

1. Command the same safe joint movement at low speed and record measured speed.
2. Repeat the movement at medium speed and record measured speed.
3. Repeat the movement at high validation speed while monitoring stability and stop distance.
4. Compare commanded speed against measured encoder feedback for all three profiles.

**Record as PASS if:** Measured speed tracks each commanded profile within tolerance and motion remains stable at low, medium, and high validation speeds.
**Record as FAIL if:** Measured speed is outside tolerance, speed does not change between profiles, motion becomes unstable, or stop distance exceeds the safe limit.
**If it fails:** Review speed profile configuration, controller scaling, and encoder feedback timing.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-HW-06
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/mechanical/TC-HW-06.md.'
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
