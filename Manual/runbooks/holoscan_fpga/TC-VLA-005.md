# TC-VLA-005 — Hololink Dual Camera Live

**Component:** Hololink Camera Pipeline &nbsp;·&nbsp; **Priority:** P1 &nbsp;·&nbsp; **Severity:** Major &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-229
**Run immediately after:** `TC-VLA-004` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Precondition:** Two cameras/sensors available through Hololink and configured for dual preview.

1. Register CAM1 and CAM2 video sinks
2. Configure dual-camera mode
3. Wait for both live signals and frame delivery
4. Verify shutdown clears both live states

**Record as PASS if:** Both camera slots become live, emit frames, and cleanly stop.
**Record as FAIL if:** Only one slot becomes live, sinks receive no frames, dual-mode configure fails, or cleanup leaves live state active.
**If it fails:** Inspect the VLA, Hololink, gesture, and hardware setup referenced by this case.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-VLA-005
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/holoscan_fpga/TC-VLA-005.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-229
```

## Path to Automation

Current state: `automation_readiness` Semi-Automatable, `automation_status` In Progress.

**Open Questions:**

1. Which parts of Hololink Camera Pipeline can already be driven by a scriptable API/SDK/CLI, and which genuinely need a human at the bench (physical setup, visual/audible judgement)?
2. What's today's pass/fail signal, and is there a sensor/log/counter equivalent that could replace the human observation?
3. Is there a safe way to simulate or mock the hardware response for a CI-only smoke check, even if the full HIL case still needs a human?

**Implementation steps once answered:**

1. Script whatever is answered "yes" to the scriptable-parts question above into a HIL test module (see `tests/test_suite_hil/testcase_hil_gates.py` for the pattern).
2. Keep a required manual sign-off step for whatever remains human-only, especially where `severity` is `Critical`.
3. Run once for real, record the result, and flip `automation_status` to `Ready` only for the parts that are genuinely automated (or keep it `Semi-Automatable` permanently if a human step will always remain).
