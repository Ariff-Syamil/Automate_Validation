# Debug Log — Thor-as-Link-Partner 25G Validation

**Status: 🔴 NEEDS FURTHER DEBUG.** This is not a `PASS`/`FAIL`/`BLOCKED`
result for `TC-FPGA-004` — it's a record of a first attempt at `STEPS.md`
that surfaced a few open questions before Step 2/3 could actually complete.
Once these are resolved, fold the final outcome back into `STEPS.md`'s
"Recording the result" section and `automate_5/runs.yaml` as normal; don't
treat this file itself as the test record.

Same legend as `README.md`: ✅ **GROUNDED** / ⚠️ **INFERRED** / ❌ **PLACEHOLDER**.

---

## Session: 2026-07-20

Commands run and raw output, in order:

```
$ ip link show | grep mgbe
2: mgbe0_0: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1466 qdisc mq state DOWN mode DEFAULT group default qlen 1000
3: mgbe1_0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1466 qdisc mq state UP mode DEFAULT group default qlen 1000
4: mgbe2_0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1466 qdisc mq state UP mode DEFAULT group default qlen 1000
5: mgbe3_0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1466 qdisc mq state UP mode DEFAULT group default qlen 1000

$ ethtool mgbe0_0
Speed: 25000Mb/s
Duplex: Full
Auto-negotiation: on
...
netlink error: Operation not permitted
Link detected: yes

$ sudo ip link set mgbe0_0 up   # (repeated for mgbe1_0, mgbe2_0, mgbe3_0)

$ ethtool mgbe0_0 mgbe1_0 mgbe2_0 mgbe3_0 2>/dev/null | grep -E "^Settings|Link detected|Speed"
Settings for mgbe0_0:
        Speed: 25000Mb/s
        Link detected: yes

$ ip -s -a addr show | grep -A1 mgbe
2: mgbe0_0 ... link/ether 3c:6d:66:fa:2f:8f ...
3: mgbe1_0 ... link/ether 3c:6d:66:fa:2f:90 ...
4: mgbe2_0 ... link/ether 3c:6d:66:fa:2f:91 ...
5: mgbe3_0 ... link/ether 3c:6d:66:fa:2f:92 ...

$ sudo tcpdump -i $IFACE -e -XX -c 20
sudo: tcpdump: command not found

$ ethtool -S $IFACE | grep -iE "crc|error|drop|fifo|frame|runt|length"
ethtool: bad command line argument(s)

$ ethtool -S $IFACE | grep -i mgbe_payload_cs_err
ethtool: bad command line argument(s)
```

## What this confirms (good news)

- **Step 0 — PASS.** `ethtool mgbe0_0` reports `Speed: 25000Mb/s`, `Duplex:
  Full`, `Link detected: yes`. Thor's QSFP28 port is already reflashed into
  25GbE mode; no `ODMDATA`/DTB work needed before continuing.
- **Duplicate-MAC caveat (`README.md` caveat #3) — clear.** All four
  `mgbeN_0` interfaces show distinct MACs (`...2f:8f`, `...2f:90`,
  `...2f:91`, `...2f:92`). The known duplicate-MAC firmware bug is not
  present on this unit.

## Open issues — why this run stalled before Step 2/3

| # | Issue | Step | Status |
|---|-------|------|--------|
| 1 | `mgbe1_0`, `mgbe2_0`, `mgbe3_0` already showed `LOWER_UP` (physical carrier) in the very first `ip link show`, *before* anything was manually brought up — only `mgbe0_0` was `NO-CARRIER`. Step 1 assumes only the leg(s) actually wired to the Avant-X board show link; here it's 3-of-4, the opposite pattern. Need to confirm with whoever wired the breakout cable whether 3 legs are genuinely connected to the DUT, or whether some legs are looped back / connected to something else on the bench. | 1 | ❌ Open |
| 2 | `ethtool mgbe0_0 mgbe1_0 mgbe2_0 mgbe3_0` (passing all four device names on one command line) is not valid `ethtool` usage — it only printed a `Settings for mgbe0_0:` block, and errors for the other three were silently swallowed by `2>/dev/null`. Need to re-run as a loop instead: `for i in mgbe0_0 mgbe1_0 mgbe2_0 mgbe3_0; do ethtool $i | grep -E "^Settings|Link detected|Speed"; done` to actually see all four legs' state. | 1 | ❌ Open — needs re-run |
| 3 | `$IFACE` in `STEPS.md` is documentation notation ("call it `$IFACE` for the rest of this runbook"), not an env var that gets set automatically. It was never exported in this shell, so `tcpdump -i $IFACE ...` and `ethtool -S $IFACE ...` expanded with an empty interface name, producing `command not found`-adjacent / `bad command line argument(s)` errors — neither is an actual DUT signal. | 2, 3 | ❌ Open — re-run after issue #1 is resolved and `export IFACE=<actual leg>` is set |
| 4 | `tcpdump` is not installed on this Thor image (`sudo: tcpdump: command not found`), independent of the `$IFACE` issue above. Needs `sudo apt install tcpdump`, or fall back to the `wireshark` alternative already noted in `STEPS.md` line 110. | 2 | ❌ Open — package missing |

## Next actions before Step 2/3 can produce real evidence

1. Physically re-verify which SFP28 leg(s) of the breakout cable are plugged
   into the Avant-X board (bench-side check, not a shell command) — resolves
   issue #1.
2. Re-run the Step 1 `ethtool` check as a loop (not a single multi-arg
   command) across all four `mgbeN_0` interfaces to get real per-leg
   `Speed`/`Link detected` output — resolves issue #2.
3. Once the correct leg is confirmed, `export IFACE=mgbeN_0` in the shell
   before running Step 2/3 commands, so `$IFACE` actually expands —
   resolves issue #3.
4. Install `tcpdump` (or switch to `wireshark`) — resolves issue #4.
5. Re-run Step 2 (frame capture) and Step 3 (`ethtool -S` CRC/error
   counters, plus `mgbe_payload_cs_err`) with the above fixed, then record
   the real result in `STEPS.md`'s "Recording the result" section /
   `automate_5/runs.yaml`.
