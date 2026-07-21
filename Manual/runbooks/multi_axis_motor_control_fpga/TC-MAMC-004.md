# TC-MAMC-004 — MAMC Fault Interlocks

**Component:** Fault Interlocks &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-237
**Run immediately after:** `TC-MAMC-001`, `TC-MAMC-002` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** Fault injection path is available for over-current, over-temperature, encoder fault, and emergency stop inputs.

1. Enable an axis at a safe command level.
2. Inject each supported fault condition one at a time.
3. Verify PWM output is disabled and fault code is latched.
4. Attempt to send a normal movement command while the fault is active.
5. Clear the fault using the documented recovery sequence and verify movement remains disabled until re-enabled.

**Record as PASS if:** Each fault disables the affected axis or all axes as specified, latches a readable fault code, rejects movement commands while active, and requires explicit recovery.
**Record as FAIL if:** Fault does not disable output, wrong fault code is reported, movement commands are accepted while faulted, or recovery bypasses the documented sequence.
**If it fails:** Keep outputs disabled and inspect fault input synchronization, latch logic, and recovery state machine.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-MAMC-004
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/multi_axis_motor_control_fpga/TC-MAMC-004.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-237
```

## Path to Automation

Current state: `automation_readiness` Semi-Automatable, `automation_status` In Progress.

**Open Questions:**

1. Which parts of Fault Interlocks can already be driven by a scriptable API/SDK/CLI, and which genuinely need a human at the bench (physical setup, visual/audible judgement)?
2. What's today's pass/fail signal, and is there a sensor/log/counter equivalent that could replace the human observation?
3. Is there a safe way to simulate or mock the hardware response for a CI-only smoke check, even if the full HIL case still needs a human?

**Implementation steps once answered:**

1. Script whatever is answered "yes" to the scriptable-parts question above into a HIL test module (see `tests/test_suite_hil/testcase_hil_gates.py` for the pattern).
2. Keep a required manual sign-off step for whatever remains human-only, especially where `severity` is `Critical`.
3. Run once for real, record the result, and flip `automation_status` to `Ready` only for the parts that are genuinely automated (or keep it `Semi-Automatable` permanently if a human step will always remain).
