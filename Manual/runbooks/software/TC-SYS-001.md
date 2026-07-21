# TC-SYS-001 — End-to-End System Flow

**Component:** End-to-End System &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-270
**Run immediately after:** `TC-FPGA-002`, `TC-FPGA-003`, `TC-FPGA-004`, `TC-FPGA-005`, `TC-FPGA-006`, `TC-SW-001`, `TC-SW-002`, `TC-SW-003`, `TC-VLA-001`, `TC-VLA-002` — do not run any other test case between that one finishing and this one starting.
**Also depends on (covered in Phase 1, already automated):** `TC-FPGA-001`

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** All listed FPGA, software, and VLA prerequisite tests have passed in the current HIL configuration.

1. Confirm all listed FPGA, software, and VLA prerequisite cases have passed in the same bench configuration.
2. Start the live vision pipeline and verify image stream health.
3. Issue a representative gesture or policy action through the VLA/control-loop path.
4. Observe command transport through software networking and motor-control layers.
5. Verify motor actuation matches the commanded action and record end-to-end latency.

**Record as PASS if:** Vision input, action generation, command transport, and motor actuation complete the scenario within latency tolerance with no dropped commands or subsystem faults.
**Record as FAIL if:** Any prerequisite subsystem regresses, action data is dropped or malformed, motor response is incorrect, latency exceeds tolerance, or a safety fault occurs.
**If it fails:** Use prerequisite results and logs to isolate the first failing subsystem, then rerun the relevant lower-level case before repeating E2E validation.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-SYS-001
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/software/TC-SYS-001.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-270
```

## Path to Automation

Current state: `automation_readiness` Manual, `automation_status` In Progress.

**Open Questions:**

1. Which of this case's prerequisite subsystems already have their own automated check, so a human only needs to start the End-to-End System portion once every dependency's latest `runs.yaml` entry is a PASS?
2. Is there a scriptable way to capture the evidence this case relies on (logs, latency numbers, transported values), even if the final pass/fail judgement itself stays human?
3. Given `automation_readiness` is already `Manual`, is full automation actually the goal here, or should this case simply be treated as "as automated as it will get" once prerequisite-checking and evidence-capture are scripted?

**Implementation steps once answered:**

1. Script the prerequisite-check (this case's `dependency` list) so a human only starts the manual portion once every dependency's latest run is a PASS.
2. Instrument logging (see `tests/test_suite_log/testcase_runtime_logger.py` for the pattern) so the human only has to judge the final result, not manually record every intermediate signal.
3. Treat this as fully covered once the previous two steps land; don't force `automation_status` toward `Ready` if a human judgement call will always remain.
