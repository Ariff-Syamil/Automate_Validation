# TC-FPGA-002 — Dual Camera Capture

**Component:** MIPI Camera Input &nbsp;·&nbsp; **Priority:** P1 &nbsp;·&nbsp; **Severity:** Major &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-229
**Also depends on (covered in Phase 1, already automated):** `TC-FPGA-001`

## Manual Procedure

**Precondition:** TC-FPGA-001 passed; two supported cameras are connected; dual-camera bitstream and clocking configuration are available.

1. Connect both supported cameras to the validated FPGA inputs.
2. Load or regenerate the dual-camera bitstream and verify clock lock for both lanes.
3. Enable both streams and route each to a distinct validation sink.
4. Monitor per-camera frame counters, frame rate, and error counters for the validation interval.
5. Stop both streams and verify no cross-stream frame mix-up occurred.

**Record as PASS if:** Both camera streams are detected, active simultaneously, maintain target frame rate, and report independent clean frame counters with no cross-stream corruption.
**Record as FAIL if:** Either stream is missing, frame rate is below tolerance, one stream starves the other, frame data is mixed, or error counters increase.
**If it fails:** Profile aggregate bandwidth, PLL timing, lane mapping, and per-stream buffer allocation.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-FPGA-002
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/holoscan_fpga/TC-FPGA-002.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-229
```
