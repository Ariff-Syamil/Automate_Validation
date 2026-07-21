# TC-FPGA-013 — Reset-During-Transfer Recovery

**Component:** Ethernet RX / SGDMA (Robustness) &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-298
**Run immediately after:** `TC-FPGA-005`, `TC-FPGA-006` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** TC-FPGA-005 and TC-FPGA-006 passed; reset can be triggered at controlled points (idle, mid-transfer, mid-burst) without a full power cycle.

1. Assert and release reset while idle with no traffic in flight; confirm firmware re-initializes SGDMA and a subsequent transfer succeeds.
2. Start a transfer, assert reset mid-transfer, release reset, and confirm firmware re-initializes and the next transfer succeeds cleanly.
3. Repeat mid-burst (reset during a multi-frame burst) and confirm recovery without stale descriptors or partial data being reported as valid.
4. Send a known-good payload immediately after each recovery and verify byte-exact capture.
5. Repeat the full sequence multiple times to confirm repeatable recovery, not a one-time fluke.

**Record as PASS if:** After reset at any point (idle, mid-transfer, mid-burst), firmware re-initializes cleanly and the next transfer is captured correctly with no stale or partial data.
**Record as FAIL if:** Reset leaves stale descriptor state, firmware hangs during re-init, or a post-reset transfer is corrupted, partial, or requires a power cycle to recover.
**If it fails:** Check descriptor/ring re-initialization sequence, firmware boot/re-init order relative to SGDMA reset release, and any missing state-clear on reset.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-FPGA-013
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/holoscan_fpga/TC-FPGA-013.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-298
```

## Path to Automation

Current state: `automation_readiness` Semi-Automatable, `automation_status` Not Ready.

Pseudo-code already drafted in [../../drafts/fpga_ingress_automation/](../../drafts/fpga_ingress_automation/) (`stimulus.py`, `readback.py`, `test_tc_fpga_ingress.py`) but unverified against real hardware.

**Open Questions:**

1. What IP address and UDP destination port does the ingress-path firmware listen on for the current reference-design bitstream? Static, or does it need DHCP/ARP setup from Thor first?
2. Does the firmware's ingress parser expect the ECB-wrapped frame (`automate5/packets/ecb_codec.py` format), or a raw/unwrapped UDP payload?
3. When you validate manually today, how do you actually inspect SGDMA/firmware state after sending a packet — UART print, JTAG/debug-bridge memory read, register dump command? Share one literal example of the real output.
4. If UART is the channel: what's the COM port naming convention, baud rate, and can you paste one real captured log line showing a successful SGDMA capture?
5. Is there a soft/register-level reset available, or is the Bellwin USB power-cycle path the only reset mechanism?

**Implementation steps once answered:**

1. Get answers to the open questions above from whoever owns the ingress-path firmware + Thor stimulus side (e.g. Sheng Li / Seow Jie).
2. Replace the placeholder/guessed pieces in `drafts/fpga_ingress_automation/stimulus.py` and `readback.py` with the confirmed behavior.
3. Move the contents into `automation/fpga/` + `tests/test_suite_fpga/`, following the same pattern as `automation/gui/` + `tests/test_suite_gui/`.
4. Flip `automation_status` from `Not Ready` to `Ready` only once the previous step is done and a real run has produced a genuine PASS.
5. (Optional) Extend `automation/gui/executor.py`'s dispatch so these cases are triggerable the same way `TC-GUI-*` cases are today.
