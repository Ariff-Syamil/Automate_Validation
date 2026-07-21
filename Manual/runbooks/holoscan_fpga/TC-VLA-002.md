# TC-VLA-002 — Gesture Motor Control

**Component:** VLA Control Loop &nbsp;·&nbsp; **Priority:** P3 &nbsp;·&nbsp; **Severity:** Major &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-235
**Run immediately after:** `TC-FPGA-002`, `TC-FPGA-003`, `TC-FPGA-004`, `TC-FPGA-005`, `TC-FPGA-006`, `TC-SW-001`, `TC-SW-002`, `TC-SW-003`, `TC-VLA-001` — do not run any other test case between that one finishing and this one starting.
**Also depends on (covered in Phase 1, already automated):** `TC-FPGA-001`

## Manual Procedure

**Precondition:** Vision, FPGA, and software communication dependencies passed; gesture input setup and motor-control HIL bench are ready.

1. Confirm vision, FPGA, and software communication dependencies passed on the current HIL bench.
2. Start the live vision pipeline and VLA/control-loop runtime.
3. Perform the documented hand gesture or action prompt sequence.
4. Record inferred action output and transported motor command values.
5. Observe motor response and compare speed/direction against the expected gesture mapping.

**Record as PASS if:** Gesture or action input produces the expected motor command, transported values match inference output, and motor speed/direction follows the mapping within tolerance.
**Record as FAIL if:** Gesture is misclassified, action output is missing, command transport corrupts values, motor speed/direction is wrong, unstable, or unsafe.
**If it fails:** Review gesture thresholds, model output, transport logs, and motor-control response before retraining or retuning.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-VLA-002
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/holoscan_fpga/TC-VLA-002.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-235
```

## Path to Automation

Current state: `automation_readiness` Manual, `automation_status` In Progress.

**Open Questions:**

1. Which of this case's prerequisite subsystems already have their own automated check, so a human only needs to start the VLA Control Loop portion once every dependency's latest `runs.yaml` entry is a PASS?
2. Is there a scriptable way to capture the evidence this case relies on (logs, latency numbers, transported values), even if the final pass/fail judgement itself stays human?
3. Given `automation_readiness` is already `Manual`, is full automation actually the goal here, or should this case simply be treated as "as automated as it will get" once prerequisite-checking and evidence-capture are scripted?

**Implementation steps once answered:**

1. Script the prerequisite-check (this case's `dependency` list) so a human only starts the manual portion once every dependency's latest run is a PASS.
2. Instrument logging (see `tests/test_suite_log/testcase_runtime_logger.py` for the pattern) so the human only has to judge the final result, not manually record every intermediate signal.
3. Treat this as fully covered once the previous two steps land; don't force `automation_status` toward `Ready` if a human judgement call will always remain.
