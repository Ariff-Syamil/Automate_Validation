# Open questions blocking real automation for TC-FPGA-010–013

Ask these to whoever owns the ingress-path firmware + Thor stimulus side
(e.g. Sheng Li / Seow Jie). Each answer maps directly to a `❌`/`⚠️` marker
in `stimulus.py` or `readback.py` — once answered, update this file with
the answer and un-mark the corresponding line in the code.

| # | Question | Blocks | Status |
|---|----------|--------|--------|
| 1 | What IP address and UDP destination port does the ingress-path firmware listen on for the current reference-design bitstream? Static, or does it need DHCP/ARP setup from Thor first? | `stimulus.TARGET_IP` / `TARGET_PORT` | Open |
| 2 | Does the firmware's ingress parser expect the **ECB-wrapped** frame (`automate5/packets/ecb_codec.py` format), or a **raw/unwrapped** UDP payload like the set-aside `thor_send_payload 1.py` script sent? | `stimulus.build_payload()` framing — the single biggest fork in this draft | Open |
| 3 | When you validate manually today, how do you actually inspect SGDMA/firmware state after sending a packet — UART print, JTAG/debug-bridge memory read, register dump command? Please share one literal example of the real output. | `readback.read_uart_log()` vs. `readback.read_descriptor_ring_via_jtag()` — which channel to build against | Open |
| 4 | If UART is the channel: what's the COM port naming convention, baud rate, and can you paste one real captured log line showing a successful SGDMA capture? | `readback.parse_sgdma_capture()` regex/format | Open |
| 5 | When a wrong-port or malformed packet is dropped today, is there *any* observable signal (counter, log line, LED) confirming it was dropped vs. silently ignored? | `test_tc_fpga_012_wrong_port_no_hang()` — "no hang" is checkable without this, but "correctly rejected" is not | Open |
| 6 | For TC-FPGA-013: is there a soft/register-level reset available, or is the Bellwin USB power-cycle path the only reset mechanism? | Whether TC-FPGA-013 can ever be more than `Semi-Automatable` | Open |

## Notes

- Do not guess at answers to unblock progress faster — the whole point of
  this draft is that guessing here previously produced a script
  (`thor_send_payload 1.py`) that was later set aside as unverified.
- Once an answer is confirmed, record who confirmed it and when (e.g. in
  a short changelog at the bottom of this file) so the provenance of each
  "grounded" fact is traceable later.
