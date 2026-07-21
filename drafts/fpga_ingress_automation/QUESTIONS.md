# Open questions blocking real automation for TC-FPGA-010–013

Ask these to whoever owns the ingress-path firmware + Thor stimulus side
(e.g. Sheng Li / Seow Jie). Each answer maps directly to a `❌`/`⚠️` marker
in `stimulus.py` or `readback.py` — once answered, update this file with
the answer and un-mark the corresponding line in the code.

**Scope reminder:** `TC-FPGA-010`–`013` are all **ingress** (host → FPGA,
Ethernet RX / SGDMA) cases. The 2026-07-20 answers below are confirmed for
**egress** (SGDMA_TX, FPGA → host) only — Seow Jie's ingress-side answers
are still pending. Treat egress facts as strong hints, not confirmation,
until Seow Jie corroborates them for the RX path.

| # | Question | Blocks | Status |
|---|----------|--------|--------|
| 1 | What IP address and UDP destination port does the ingress-path firmware listen on for the current reference-design bitstream? Static, or does it need DHCP/ARP setup from Thor first? | `stimulus.TARGET_IP` / `TARGET_PORT` | Partially answered (egress side only) — see below. Ingress side still **Open**, pending Seow Jie. |
| 2 | Does the firmware's ingress parser expect the **ECB-wrapped** frame (`automate5/packets/ecb_codec.py` format), or a **raw/unwrapped** UDP payload like the set-aside `thor_send_payload 1.py` script sent? | `stimulus.build_payload()` framing — the single biggest fork in this draft | Partially answered (egress side points away from ECB) — see below. Ingress payload framing still **Open**, pending Seow Jie. |
| 3 | When you validate manually today, how do you actually inspect SGDMA/firmware state after sending a packet — UART print, JTAG/debug-bridge memory read, register dump command? Please share one literal example of the real output. | `readback.read_uart_log()` vs. `readback.read_descriptor_ring_via_jtag()` — which channel to build against | Partially answered (egress side uses a packet-capture/decode tool, not UART, per Sheng Li) — see below. Whether ingress uses the same mechanism is **Open**, pending Seow Jie/RTL detail. |
| 4 | If UART is the channel: what's the COM port naming convention, baud rate, and can you paste one real captured log line showing a successful SGDMA capture? | `readback.parse_sgdma_capture()` regex/format | Open. (May turn out moot if ingress verification also goes through the same packet-capture tool as egress, rather than UART — see Q3.) |
| 5 | When a wrong-port or malformed packet is dropped today, is there *any* observable signal (counter, log line, LED) confirming it was dropped vs. silently ignored? | `test_tc_fpga_012_wrong_port_no_hang()` — "no hang" is checkable without this, but "correctly rejected" is not | Open |
| 6 | For TC-FPGA-013: is there a soft/register-level reset available, or is the Bellwin USB power-cycle path the only reset mechanism? | Whether TC-FPGA-013 can ever be more than `Semi-Automatable` | Open |
| 7 | What physical link/interface does Thor use to reach the FPGA (which NIC, what link speed)? *(New question, raised by Sheng Li's answer.)* | `stimulus.send_udp_payload()` — whether an explicit interface bind is needed alongside IP/port | Tentatively answered (egress side): "should be through 25G QSFP" — Sheng Li was not fully certain. Treat as unconfirmed until verified. |

## Answers received — 2026-07-20, via Sheng Li (egress/SGDMA_TX only)

Sheng Li shared one real, decoded packet capture from the **egress**
(SGDMA_TX) direction, explicitly noting ingress is still unconfirmed
(Seow Jie in progress):

```json
{"capture_time": 1784102093.4898088, "direction": "tx", "eth": {"dst_mac": "ca:fe:c0:ff:ee:00", "src_mac": "3c:6d:66:fa:2f:8f", "ethertype": "0x0800"}, "ip": {"version": 4, "header_length": 20, "total_length": 92, "ttl": 64, "protocol": 17, "src": "192.168.0.101", "dst": "192.168.0.2"}, "udp": {"src_port": 42199, "dst_port": 5000, "length": 72, "checksum": 33297}, "packet_type": "sgdma_tx", "payload_length": 64, "fields": {"payload_length": 64, "marker_le": "0xDEADBEEFCAFEF00D", "marker_repeats_cleanly": true}, "payload_hex": "0df0fecaefbeadde0df0fecaefbeadde0df0fecaefbeadde0df0fecaefbeadde0df0fecaefbeadde0df0fecaefbeadde0df0fecaefbeadde0df0fecaefbeadde"}
```

What this tells us (egress side):

- **IP pair:** FPGA = `192.168.0.101`, host = `192.168.0.2`.
- **Port:** UDP dst port `5000` for SGDMA_TX traffic.
- **Payload framing:** the 64-byte payload is the marker `0xDEADBEEFCAFEF00D`
  (little-endian) repeated 8×, with **no ECB header, no address field, no
  sequence number** — just raw marker bytes. This is evidence against the
  ECB-wrapped hypothesis (option (a) in `stimulus.py`'s docstring), at
  least for this direction.
- **Identification/verification (partial):** Sheng Li said this is
  recognized via `packet_type == "sgdma_tx"` and `dst_port == 5000`, plus
  unspecified "other checking" — deferred to Seow Jie for RTL-level detail.
- **This JSON schema itself was searched for** across `automate_validation`,
  `Automate5`, and `Board Farm` on this machine — **no match**. Whatever
  tool produced it (packet sniffer + decoder, most likely) is not in any
  local checkout; only the one example output has been shared so far, not
  the tool itself.
- **Physical link (Q7):** Sheng Li believes traffic goes over a 25G QSFP
  interface on Thor, but was explicitly unsure ("Not sure. But should be
  through 25GB QSFP").

## Next steps

1. **Get Seow Jie's ingress-side mirror of this same information**: the
   host → FPGA IP/port pair, whether the ingress payload is framed the
   same way (raw marker-style, no ECB), and whether ingress traffic is
   identified/verified the same way (a `packet_type`/port check plus RTL
   detail) or differently.
2. **Ask Sheng Li for the actual capture/decode tool**, not just one
   example JSON output — if it can decode ingress (RX) traffic the same
   way it decodes this egress (TX) example, it may replace the
   UART-log-based `readback.py` design entirely. Specifically ask: where
   does it run (on Thor, on a tap/mirror port, inline in firmware?), what
   produces `capture_time`/`packet_type`, and can it be pointed at RX
   traffic.
3. **Confirm whether ingress verification is capture-based (like egress)
   or firmware/UART-based** — this determines whether `readback.py` should
   be rebuilt around decoding captured packets (mirroring the JSON schema
   above) instead of parsing UART log lines.
4. **Confirm the 25G QSFP physical link** (Q7) and, if true, find out
   whether stimulus traffic needs to be sent from a specific bound
   interface on Thor, or a plain `socket.sendto()` to the FPGA's IP is
   sufficient regardless of interface.
5. Once 1–4 land, re-open `stimulus.py`/`readback.py` and replace the
   remaining ❌/⚠️ markers for the ingress path specifically — the egress
   facts above are strong hints but should not be silently assumed to
   apply to ingress without Seow Jie's confirmation.

## Notes

- Do not guess at answers to unblock progress faster — the whole point of
  this draft is that guessing here previously produced a script
  (`thor_send_payload 1.py`) that was later set aside as unverified.
- Once an answer is confirmed, record who confirmed it and when (e.g. in
  a short changelog at the bottom of this file) so the provenance of each
  "grounded" fact is traceable later.
