# TC-MAMC-003 — MAMC PWM Current Loop

**Component:** PWM and Current Loop &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-237
**Run immediately after:** `TC-MAMC-001`, `TC-MAMC-002` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** Motor drivers are connected to dummy load or safe test motor; current limits and PWM frequency are configured.

1. Enable one axis at low duty cycle with the safe load connected.
2. Measure PWM frequency, duty cycle, and dead-time using the configured instrumentation.
3. Command a step change in current or torque setpoint.
4. Record loop response, overshoot, settling time, and current-limit behavior.
5. Repeat for each supported axis at safe validation levels.

**Record as PASS if:** PWM frequency and duty cycle match configuration, current-loop response remains stable, overshoot is within tolerance, and current limits are enforced for every axis.
**Record as FAIL if:** PWM timing is wrong, dead-time is unsafe, loop oscillates, overshoot exceeds tolerance, current limit is not enforced, or axes behave inconsistently.
**If it fails:** Review PWM timer configuration, current-sense scaling, PI gains, and current-limit comparator wiring.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-MAMC-003
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/multi_axis_motor_control_fpga/TC-MAMC-003.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-237
```

## Path to Automation

Current state: `automation_readiness` Semi-Automatable, `automation_status` In Progress.

**Open Questions:**

1. Which parts of PWM and Current Loop can already be driven by a scriptable API/SDK/CLI, and which genuinely need a human at the bench (physical setup, visual/audible judgement)?
2. What's today's pass/fail signal, and is there a sensor/log/counter equivalent that could replace the human observation?
3. Is there a safe way to simulate or mock the hardware response for a CI-only smoke check, even if the full HIL case still needs a human?

**Implementation steps once answered:**

1. Script whatever is answered "yes" to the scriptable-parts question above into a HIL test module (see `tests/test_suite_hil/testcase_hil_gates.py` for the pattern).
2. Keep a required manual sign-off step for whatever remains human-only, especially where `severity` is `Critical`.
3. Run once for real, record the result, and flip `automation_status` to `Ready` only for the parts that are genuinely automated (or keep it `Semi-Automatable` permanently if a human step will always remain).
