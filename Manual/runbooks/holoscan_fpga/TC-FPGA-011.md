# TC-FPGA-011 — Back-to-Back Burst / Descriptor Ring Wraparound

**Component:** Ethernet RX / SGDMA (Robustness) &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-298
**Run immediately after:** `TC-FPGA-005`, `TC-FPGA-006` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** TC-FPGA-005 and TC-FPGA-006 passed; descriptor ring depth is known; THOR script supports configurable inter-frame gap and burst count.

1. Configure THOR to send bursts of N frames at minimum inter-frame gap, sweeping N across 1, a mid-size burst, and a burst exceeding the descriptor ring depth to force wraparound.
2. Trigger each burst and allow SGDMA to capture all frames into the configured descriptor ring.
3. Have firmware walk every completed descriptor and verify payload, length, and ordering for each frame in the burst.
4. Repeat the largest burst size using the fabric-RTL pattern generator for cross-source confirmation.
5. Record any dropped, reordered, or corrupted frames per burst size.

**Record as PASS if:** All frames in every burst size are captured in order with correct payload and length, including bursts that wrap the descriptor ring, with no dropped or corrupted frames.
**Record as FAIL if:** Any frame in a burst is dropped, reordered, duplicated, or corrupted, or the descriptor ring stalls/errors on wraparound.
**If it fails:** Inspect descriptor ring pointer management, FIFO occupancy during bursts, and completion-interrupt handling in firmware.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-FPGA-011
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/holoscan_fpga/TC-FPGA-011.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-298
```

## Path to Automation

Current state: `automation_readiness` Automatable, `automation_status` Not Ready.

Pseudo-code already drafted in [../../drafts/fpga_ingress_automation/](../../drafts/fpga_ingress_automation/) (`stimulus.py`, `readback.py`, `test_tc_fpga_ingress.py`) but unverified against real hardware.

**Open Questions:**

1. What IP address and UDP destination port does the ingress-path firmware listen on for the current reference-design bitstream? Static, or does it need DHCP/ARP setup from Thor first?
2. Does the firmware's ingress parser expect the ECB-wrapped frame (`automate5/packets/ecb_codec.py` format), or a raw/unwrapped UDP payload?
3. When you validate manually today, how do you actually inspect SGDMA/firmware state after sending a packet — UART print, JTAG/debug-bridge memory read, register dump command? Share one literal example of the real output.
4. If UART is the channel: what's the COM port naming convention, baud rate, and can you paste one real captured log line showing a successful SGDMA capture?

**Implementation steps once answered:**

1. Get answers to the open questions above from whoever owns the ingress-path firmware + Thor stimulus side (e.g. Sheng Li / Seow Jie).
2. Replace the placeholder/guessed pieces in `drafts/fpga_ingress_automation/stimulus.py` and `readback.py` with the confirmed behavior.
3. Move the contents into `automation/fpga/` + `tests/test_suite_fpga/`, following the same pattern as `automation/gui/` + `tests/test_suite_gui/`.
4. Flip `automation_status` from `Not Ready` to `Ready` only once the previous step is done and a real run has produced a genuine PASS.
5. (Optional) Extend `automation/gui/executor.py`'s dispatch so these cases are triggerable the same way `TC-GUI-*` cases are today.
