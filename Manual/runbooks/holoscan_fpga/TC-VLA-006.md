# TC-VLA-006 — VLA Policy Action Response

**Component:** VLA Policy Server &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-290
**Run immediately after:** `TC-SYS-003` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** VLA policy server or simulator reachable; synthetic observation fixture available.

1. Connect to configured VLA policy endpoint
2. Send synthetic observation and prompt
3. Receive action chunk response
4. Validate shape, numeric ranges, timeout behavior, and motor command conversion

**Record as PASS if:** Policy service returns valid action within timeout and failure paths map to coded errors.
**Record as FAIL if:** Timeout, malformed action, invalid range, missing prompt handling, or no coded error on failure.
**If it fails:** Inspect the VLA, Hololink, gesture, and hardware setup referenced by this case.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-VLA-006
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/holoscan_fpga/TC-VLA-006.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-290
```

## Path to Automation

Current state: `automation_readiness` Semi-Automatable, `automation_status` In Progress.

**Open Questions:**

1. Which parts of VLA Policy Server can already be driven by a scriptable API/SDK/CLI, and which genuinely need a human at the bench (physical setup, visual/audible judgement)?
2. What's today's pass/fail signal, and is there a sensor/log/counter equivalent that could replace the human observation?
3. Is there a safe way to simulate or mock the hardware response for a CI-only smoke check, even if the full HIL case still needs a human?

**Implementation steps once answered:**

1. Script whatever is answered "yes" to the scriptable-parts question above into a HIL test module (see `tests/test_suite_hil/testcase_hil_gates.py` for the pattern).
2. Keep a required manual sign-off step for whatever remains human-only, especially where `severity` is `Critical`.
3. Run once for real, record the result, and flip `automation_status` to `Ready` only for the parts that are genuinely automated (or keep it `Semi-Automatable` permanently if a human step will always remain).
