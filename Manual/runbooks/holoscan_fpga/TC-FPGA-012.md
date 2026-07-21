# TC-FPGA-012 — Wrong-Port UDP and Malformed Frame Rejection

**Component:** Ethernet RX / SGDMA (Robustness) &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-298
**Run immediately after:** `TC-FPGA-005` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** TC-FPGA-005 passed; THOR script can target arbitrary/invalid UDP destination ports and send malformed frames.

1. Send a valid payload to the expected UDP destination port and confirm normal capture as a baseline.
2. Send a packet to an unexpected/wrong UDP destination port and confirm it is dropped, not captured into the buffer.
3. Send a short/runt frame and a frame with a bad checksum, confirming both are dropped.
4. Immediately after each negative case, send another valid-port packet and confirm it is captured correctly.
5. Repeat the wrong-port and malformed cases back-to-back several times to confirm the FSM never latches into a stuck state.

**Record as PASS if:** Wrong-port and malformed packets are dropped with no capture, the RX FSM returns to idle every time, and subsequent valid packets are always captured correctly.
**Record as FAIL if:** The FSM hangs or stops accepting valid packets after a wrong-port/malformed packet, a wrong-port packet is incorrectly captured, or recovery requires a manual reset.
**If it fails:** Inspect UDP/IP header filter logic and RX FSM state transitions on the drop path; check for a missing default/idle transition.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-FPGA-012
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/holoscan_fpga/TC-FPGA-012.md.'
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
5. When a wrong-port or malformed packet is dropped today, is there any observable signal (counter, log line, LED) confirming it was dropped vs. silently ignored?

**Implementation steps once answered:**

1. Get answers to the open questions above from whoever owns the ingress-path firmware + Thor stimulus side (e.g. Sheng Li / Seow Jie).
2. Replace the placeholder/guessed pieces in `drafts/fpga_ingress_automation/stimulus.py` and `readback.py` with the confirmed behavior.
3. Move the contents into `automation/fpga/` + `tests/test_suite_fpga/`, following the same pattern as `automation/gui/` + `tests/test_suite_gui/`.
4. Flip `automation_status` from `Not Ready` to `Ready` only once the previous step is done and a real run has produced a genuine PASS.
5. (Optional) Extend `automation/gui/executor.py`'s dispatch so these cases are triggerable the same way `TC-GUI-*` cases are today.
