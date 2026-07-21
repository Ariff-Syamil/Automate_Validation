# TC-FPGA-009 — Dual-Camera Focus & Sharpness Calibration

**Component:** MIPI Camera Input (Image Quality) &nbsp;·&nbsp; **Priority:** P2 &nbsp;·&nbsp; **Severity:** Minor &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-229
**Run immediately after:** `TC-FPGA-002` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Precondition:** Dual-camera capture passes (TC-FPGA-002); focus/calibration tooling available with an objective sharpness metric.

1. Enable dual-camera stereo mode with both streams live.
2. Capture a reference test-chart image on each stream.
3. Compute an objective sharpness/MTF score for each captured frame.
4. Compare each stream's score against the agreed minimum threshold.
5. Record per-camera scores for trend tracking across future calibration passes.

**Record as PASS if:** Both camera streams meet or exceed the minimum sharpness/MTF threshold with no visible blur.
**Record as FAIL if:** Either stream's sharpness score falls below threshold, or visible blur persists after focus tuning.
**If it fails:** Re-run focus tuning procedure, check lens seating and back-focus distance, and re-measure.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-FPGA-009
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/holoscan_fpga/TC-FPGA-009.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-229
```
