# TC-FPGA-010 — Ingress UDP Payload Size Sweep

**Component:** Ethernet RX / SGDMA (Robustness) &nbsp;·&nbsp; **Priority:** P1 &nbsp;·&nbsp; **Severity:** Major &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-298
**Run immediately after:** `TC-FPGA-005`, `TC-FPGA-006` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Precondition:** TC-FPGA-005 and TC-FPGA-006 passed; THOR Python traffic generator and fabric-RTL pattern generator are both available on the same bitstream; SGDMA descriptor/memory readback harness is in place.

1. Define the payload size sweep list, covering minimum payload, tkeep-width boundary values (width-1, width, width+1), a typical mid-size payload, and MTU-sized payload.
2. For each size, send a deterministic payload from the THOR Python script over UDP to the FPGA.
3. Repeat the same sweep using the fabric-RTL pattern generator with matching frame lengths.
4. For each transfer, have firmware read back the SGDMA buffer and compare byte-for-byte against the expected payload and length.
5. Record pass/fail per payload size and per source (THOR vs. pattern generator).

**Record as PASS if:** Every payload size in the sweep is captured with correct length and byte-exact content from both the THOR and pattern-generator sources, with no SGDMA descriptor or bus errors.
**Record as FAIL if:** Any payload size is truncated, padded incorrectly, misaligned at a tkeep boundary, corrupted, or reports a descriptor/bus error.
**If it fails:** Check tkeep/tlast handling at the failing size, the descriptor length field, and buffer alignment in the SGDMA RTL.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-FPGA-010
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/holoscan_fpga/TC-FPGA-010.md.'
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
