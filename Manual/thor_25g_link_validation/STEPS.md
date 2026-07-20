# Manual Runbook — Thor-as-Link-Partner 25G Validation

Run these steps in order, on the Jetson AGX Thor host (SSH or console),
with the QSFP28-to-4×SFP28 breakout cable connected to the Avant-X board.
Fill in the `❌ PLACEHOLDER` blanks for your setup before running.

Each step notes which `TC-FPGA-004` field it produces evidence for, so you
can copy the outcome straight into a manual run note / `runs.yaml` entry
when done.

---

## Step 0 — Confirm Thor's QSFP port is actually in 25GbE mode

✅ **GROUNDED**: Thor's QSFP28 port defaults to **10GbE**. Reaching 25GbE
requires either an `ODMDATA` flash-config change
(`jetson-agx-thor-devkit.conf`) or a kernel DTSI + BPMP DTB patch, followed
by a **full reflash**. There is no way to get 25G at runtime only. If this
hasn't been done, every later step will show link-down or 10G, and that's
expected — it's not a DUT problem.

```bash
ip link show | grep mgbe
ethtool mgbe0_0   # repeat for mgbe1_0, mgbe2_0, mgbe3_0
```

Look at the `Speed:` field once link is up.

**Expected output on pass:**

```
Settings for mgbe0_0:
        Speed: 25000Mb/s
        Duplex: Full
        Link detected: yes
```

- If `Speed: 25000Mb/s` on the connected leg → reflash already done, continue to Step 1.
- If `Speed: 10000Mb/s` or no link at all → Thor is still in default 10G mode.
  Confirm with whoever flashed this Thor unit whether `ODMDATA` was set to
  `uphy1-config-8,mgbe0-speed-3,mgbe1-speed-3,mgbe2-speed-3,mgbe3-speed-3`
  (or the DTB-patch equivalent) — this is a reflash-owner question, not
  something fixable from a running shell.

**Maps to `TC-FPGA-004` fail condition:** *"Link does not come up, negotiates
the wrong speed."*

---

## Step 1 — Identify which MGBE interface maps to your connected leg

⚠️ **INFERRED**: a QSFP28→4×SFP28 breakout cable typically maps lane 0→leg 1,
lane 1→leg 2, etc., corresponding to `mgbe0_0`...`mgbe3_0` in order — but
this isn't confirmed for your specific cable/wiring, so don't assume which
`mgbeN_0` is "yours" until you check.

```bash
sudo ip link set mgbe0_0 up
sudo ip link set mgbe1_0 up
sudo ip link set mgbe2_0 up
sudo ip link set mgbe3_0 up
ethtool mgbe0_0 mgbe1_0 mgbe2_0 mgbe3_0 2>/dev/null | grep -E "^Settings|Link detected|Speed"
```

Only the leg(s) actually plugged into the Avant-X board should show
`Link detected: yes`. Record which `mgbeN_0` that is — call it
`$IFACE` for the rest of this runbook.

**Expected output on pass:** exactly one (or however many legs you
physically connected) of the four blocks shows `Link detected: yes` /
`Speed: 25000Mb/s`; the rest show `Link detected: no`, e.g.:

```
Settings for mgbe0_0:
        Speed: 25000Mb/s
        Link detected: yes
Settings for mgbe1_0:
        Speed: Unknown!
        Link detected: no
Settings for mgbe2_0:
        Speed: Unknown!
        Link detected: no
Settings for mgbe3_0:
        Speed: Unknown!
        Link detected: no
```

While you're here, also check for the known duplicate-MAC issue mentioned
in `README.md`:

```bash
ip -s -a addr show | grep -A1 mgbe
```

**Expected output on pass:** all four `mgbeN_0` interfaces show distinct
MAC addresses. If two `mgbeN_0` interfaces share the same MAC address,
that's a Thor firmware bug unrelated to the DUT — note it, don't debug it
as a DUT issue.

---

## Step 2 — Capture the actual frames

Now that link is up on `$IFACE`, look at real traffic content:

```bash
sudo tcpdump -i $IFACE -e -XX -c 20
```

Or, if a desktop session is available on Thor: `sudo apt install wireshark`
and capture on `$IFACE` directly.

Check: source/destination MAC, EtherType, frame length, and payload pattern
against whatever the Avant-X board is expected to be transmitting (a
pattern generator or known test payload — you don't need to know *how* the
FPGA builds it, just what it should look like on the wire).

**Expected output on pass:** 20 frames print without the capture hanging,
each with a consistent source/destination MAC, a sensible EtherType (e.g.
`0x0800` for IPv4), and a frame length matching the expected transmit
pattern, e.g.:

```
14:32:07.112233 aa:bb:cc:dd:ee:01 > aa:bb:cc:dd:ee:02, ethertype IPv4 (0x0800), length 1518: ...
        0x0000:  aabb ccdd ee02 aabb ccdd ee01 0800 4500
        0x0010:  05dc 0001 0000 4011 ...
14:32:07.112240 aa:bb:cc:dd:ee:01 > aa:bb:cc:dd:ee:02, ethertype IPv4 (0x0800), length 1518: ...
```

This is a sanity check, not a hard pass/fail gate like Step 3 — pass here
just means frames are actually flowing and their headers look sane and
consistent, not garbled or truncated frame-to-frame.

**Maps to `TC-FPGA-004` step:** *"Attempt link bring-up and record negotiated
speed/status."*

---

## Step 3 — Check the driver's error counters (this is the definitive pass/fail signal)

```bash
ethtool -S $IFACE | grep -iE "crc|error|drop|fifo|frame|runt|length"
```

Also check specifically for the MACsec-related counter called out in
`README.md`:

```bash
ethtool -S $IFACE | grep -i mgbe_payload_cs_err
```

**Expected output on pass:** every matching counter reads `0`, e.g.:

```
rx_crc_errors: 0
rx_frame_errors: 0
rx_fifo_errors: 0
rx_length_errors: 0
tx_errors: 0
```

**Pass:** all of the above are zero, or non-incrementing across repeated
reads while traffic is flowing. Same expectation for
`mgbe_payload_cs_err: 0`.

**Fail (maps to `TC-FPGA-004` fail condition *"CRC errors exceed
tolerance, or packets are lost"*):** any of these counters actively
incrementing.

This step alone — zero/non-incrementing CRC and frame-error counters,
measured by Thor's own independent MAC — is the strongest "the Avant-X
board is generating well-formed, correctly-CRC'd 25GbE frames" evidence you
can get without any knowledge of the FPGA's internal design.

---

## Step 4 — Stress test (optional, throughput signal — read the caveat first)

⚠️ Before running this step, re-read caveat #2 in `README.md`. Thor's own
25G software path is documented (NVIDIA dev forum, 2025) to cap around
~10–17 Gbps per lane even on a fully healthy 25G link, due to a known
issue on NVIDIA's side. **Use this step for "is throughput stable and
loss-free," not "does it hit 24 Gbps."**

```bash
sudo ifconfig $IFACE down mtu 9000 up

# Enable threaded NAPI (recommended by NVIDIA's own tuning doc)
sudo sh -c "echo 1 > /sys/class/net/$IFACE/threaded"

# On the Avant-X/traffic-source side, then on Thor as receiver:
iperf3 -s

# Or, if Thor is the sender toward a receiver on the other end:
iperf3 -c <peer_ip> -t 30
```

**Expected output on pass:** a steady per-interval bitrate with `Retr`
(retransmits) staying at or near `0` for the whole run, e.g.:

```
[ ID] Interval           Transfer     Bitrate         Retr
[  5]   0.00-1.00   sec  1.50 GBytes  12.9 Gbits/sec    0
[  5]   1.00-2.00   sec  1.48 GBytes  12.7 Gbits/sec    0
[  5]   2.00-3.00   sec  1.51 GBytes  13.0 Gbits/sec    0
[  5]  29.00-30.00  sec  1.49 GBytes  12.8 Gbits/sec    0
[  5]   0.00-30.00  sec  44.3 GBytes  12.8 Gbits/sec           sender
```

**Pass:** throughput is stable (no big swings/drops) and loss-free for the
duration of the run, whatever the absolute number is — per the caveat
above, ~10-17 Gbits/sec here is an expected Thor-side ceiling, not a fail.

**Fail (maps to `TC-FPGA-004` fail condition *"throughput is unstable"*):**
throughput that fluctuates wildly, drops to near-zero intermittently, or is
accompanied by retransmits (TCP) — as opposed to just being below the
theoretical 25 Gbps line rate, which per the caveat above is expected on
Thor today.

---

## Recording the result

Once done, translate the above into a manual entry consistent with the
existing `automate_5/runs.yaml` format for `TC-FPGA-004`, e.g.:

```yaml
- test_case_id: TC-FPGA-004
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual Thor-link-partner validation per drafts/thor_25g_link_validation/STEPS.md.
    Link up on <mgbeN_0> at 25000Mb/s. CRC/frame-error counters non-incrementing
    over N-second capture. iperf3 stable at X Gbps (Thor SW-path ceiling per
    known NVIDIA issue, not attributed to DUT).'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-229
```

Do not flip `automation_status` for `TC-FPGA-004` in
`automate_5/holoscan_fpga/test_cases.yaml` based on this — this is a manual
procedure, not an automated script, so the case stays `Semi-Automatable`/
`In Progress` unless someone later wires this into real automation (same
"path to real" gate described in `../../drafts/fpga_ingress_automation/README.md`).
