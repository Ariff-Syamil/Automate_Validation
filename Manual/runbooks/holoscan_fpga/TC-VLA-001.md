# TC-VLA-001 — Live Vision Pipeline

**Component:** Holoscan Vision &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-268
**Run immediately after:** `TC-FPGA-002` — do not run any other test case between that one finishing and this one starting.
**Also depends on (covered in Phase 1, already automated):** `TC-FPGA-001`

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** Camera capture dependencies passed; Holoscan runtime, GPU, and pipeline configuration are available.

1. Start the Holoscan vision pipeline with the validated camera input configuration.
2. Confirm the pipeline receives frames from the capture source.
3. Monitor FPS, per-stage latency, GPU utilization, and dropped-frame counters.
4. Run the pipeline for the validation interval using representative scene input.
5. Stop the pipeline and collect logs for latency and stability review.

**Record as PASS if:** Pipeline runs for the validation interval at target FPS, latency remains within tolerance, GPU utilization is stable, and no crashes or frame drops occur.
**Record as FAIL if:** Pipeline crashes, frame input stalls, FPS falls below target, latency exceeds tolerance, GPU errors occur, or dropped-frame counters increase.
**If it fails:** Profile GPU kernels, Holoscan stage timings, capture source health, and memory transfer bottlenecks.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-VLA-001
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/holoscan_fpga/TC-VLA-001.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-268
```

## Path to Automation

Current state: `automation_readiness` Semi-Automatable, `automation_status` In Progress.

**Open Questions:**

1. Which parts of Holoscan Vision can already be driven by a scriptable API/SDK/CLI, and which genuinely need a human at the bench (physical setup, visual/audible judgement)?
2. What's today's pass/fail signal, and is there a sensor/log/counter equivalent that could replace the human observation?
3. Is there a safe way to simulate or mock the hardware response for a CI-only smoke check, even if the full HIL case still needs a human?

**Implementation steps once answered:**

1. Script whatever is answered "yes" to the scriptable-parts question above into a HIL test module (see `tests/test_suite_hil/testcase_hil_gates.py` for the pattern).
2. Keep a required manual sign-off step for whatever remains human-only, especially where `severity` is `Critical`.
3. Run once for real, record the result, and flip `automation_status` to `Ready` only for the parts that are genuinely automated (or keep it `Semi-Automatable` permanently if a human step will always remain).
