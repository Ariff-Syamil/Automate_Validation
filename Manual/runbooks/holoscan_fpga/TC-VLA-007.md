# TC-VLA-007 — Holoscan Demo Container Live Stream Verification

**Component:** Holoscan Sensor Bridge Demo Container &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-229
**Run immediately after:** `TC-FPGA-004`, `TC-VLA-001` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** 25G link established; Holoscan Sensor Bridge Demo Container image built and deployed on Jetson AGX Thor.

1. Build the Holoscan Sensor Bridge Demo Container image against the current reference design.
2. Deploy and launch the container on the flashed Jetson AGX Thor.
3. Confirm the container connects to the FPGA over the 25G Ethernet link.
4. Verify live video renders in the demo viewer with expected frame rate.
5. Run for the validation interval and check for stalls, disconnects, or container crashes.

**Record as PASS if:** Container builds without errors, connects over 25G, and displays a stable live stream for the full validation interval with no crashes or disconnects.
**Record as FAIL if:** Container fails to build, fails to connect over 25G, stream does not render, stalls, or the container crashes during the run.
**If it fails:** Check container build logs, Thor-to-FPGA network reachability, and Hololink camera pipeline health (see TC-VLA-004/005).

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-VLA-007
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/holoscan_fpga/TC-VLA-007.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-229
```
