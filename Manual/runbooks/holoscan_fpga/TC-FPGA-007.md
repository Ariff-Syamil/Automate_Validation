# TC-FPGA-007 — 25G Sustained Torn-Rate Soak Test

**Component:** Ethernet RX / SGDMA (25G Optimization) &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-298
**Run immediately after:** `TC-FPGA-004`, `TC-FPGA-005` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** 25G link established (TC-FPGA-004 passed); real motor/sensor traffic source available (not synthetic test patterns); torn-rate counters instrumented in RTL/firmware.

1. Confirm 25G link is up and stable (TC-FPGA-004 passed).
2. Replace synthetic test-pattern generator with real motor/sensor application traffic.
3. Drive sustained, MTU-sized traffic at full 25G line rate for the soak duration.
4. Monitor SGDMA descriptor completion, buffer occupancy, and torn/dropped packet counters throughout.
5. Confirm measured sustained bandwidth against target and record final torn-rate count.

**Record as PASS if:** Torn-rate counter stays at zero (or within agreed tolerance) for the full soak duration, sustained bandwidth meets target, and no descriptor completion errors occur.
**Record as FAIL if:** Torn/dropped packets accumulate, sustained bandwidth falls below target, buffers overflow/underrun, or descriptor completions stall or error out.
**If it fails:** Profile SGDMA buffer depth, drain timing, and completion-handling logic in the custom RTL; compare against 10G baseline torn-rate counters.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-FPGA-007
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/holoscan_fpga/TC-FPGA-007.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-298
```
