# TC-SYS-005 — HIL Camera VLA EtherCAT Motor Command

**Component:** End-to-End System &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-270
**Run immediately after:** `TC-VLA-001`, `TC-SW-003` — do not run any other test case between that one finishing and this one starting.
**Also depends on (covered in Phase 1, already automated):** `TC-SW-019`

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** Hololink board, cameras, VLA policy server, EtherCAT hardware, and motor rig connected and calibrated.

1. Start Hololink camera pipeline
2. Start VLA policy server
3. Submit known prompt or gesture
4. Capture action command and encoded packet
5. Observe motor response against safe envelope

**Record as PASS if:** Live input produces valid VLA action, correct packet, and safe motor response.
**Record as FAIL if:** Camera not live, VLA timeout, malformed action, packet mismatch, dropped command, or unsafe motion.
**If it fails:** Inspect the referenced Automate5 module, fixture, and pytest output.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-SYS-005
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/software/TC-SYS-005.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-270
```

## Path to Automation

Current state: `automation_readiness` Semi-Automatable, `automation_status` In Progress.

**Open Questions:**

1. Which parts of End-to-End System can already be driven by a scriptable API/SDK/CLI, and which genuinely need a human at the bench (physical setup, visual/audible judgement)?
2. What's today's pass/fail signal, and is there a sensor/log/counter equivalent that could replace the human observation?
3. Is there a safe way to simulate or mock the hardware response for a CI-only smoke check, even if the full HIL case still needs a human?

**Implementation steps once answered:**

1. Script whatever is answered "yes" to the scriptable-parts question above into a HIL test module (see `tests/test_suite_hil/testcase_hil_gates.py` for the pattern).
2. Keep a required manual sign-off step for whatever remains human-only, especially where `severity` is `Critical`.
3. Run once for real, record the result, and flip `automation_status` to `Ready` only for the parts that are genuinely automated (or keep it `Semi-Automatable` permanently if a human step will always remain).
