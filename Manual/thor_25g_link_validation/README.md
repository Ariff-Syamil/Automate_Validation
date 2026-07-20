# Thor-as-Link-Partner 25G Validation — DRAFT (manual procedure, not automation)

**Status: DRAFT. This is a manual runbook for a human to execute on Thor, not
automated code.** Nothing in this folder is wired into `automation/` or
`tests/`.

## What this is

Maps to `TC-FPGA-004` — *25G Ethernet Link Bring-Up* — in
`automate_5/holoscan_fpga/test_cases.yaml` (owner: Sheng Li). That test case
has run `BLOCKED` on every recorded run in `automate_5/runs.yaml`
(`Real_Run_03`, `Real_Run_06`, `Real_Run_09`) with the note *"Hardware-dependent
test case with no automation script."* This is a step-by-step black-box
procedure someone can follow by hand on the Jetson AGX Thor host to actually
produce a manual PASS/FAIL/BLOCKED result for that case, without needing any
knowledge of the Avant-X RTL/firmware internals.

It also feeds `TC-FPGA-007` (*25G Sustained Torn-Rate Soak Test*), which
depends on `TC-FPGA-004` passing first — see the throughput caveat below
before using this to gate that case.

See `STEPS.md` for the actual runbook. See `DEBUG_LOG.md` for a record of
in-progress debugging sessions where a run stalled before completion —
check there first if you're resuming a partial attempt.

## Why Thor, and why this is safe to run without RTL knowledge

Thor's QSFP28 port is a real Linux NIC (NVIDIA's own MGBE MAC/PCS silicon and
driver), exposed as `mgbe0_0`–`mgbe3_0`. Every signal used below —
`ethtool` link/speed state, `ethtool -S` CRC/error counters, `tcpdump`
capture — comes from that independent NVIDIA-side receiver, not from
anything instrumented inside the Avant-X FPGA. You're purely observing what
the DUT puts on the wire and what an independent, known-good MAC measured.

## File legend (same convention as `../../drafts/fpga_ingress_automation/README.md`)

- ✅ **GROUNDED** — confirmed against NVIDIA's own docs or developer-forum
  reports (cited inline in `STEPS.md`)
- ⚠️ **INFERRED** — reasonable assumption, not yet confirmed against *this*
  specific Thor unit / cable / bitstream
- ❌ **PLACEHOLDER** — must be filled in / confirmed for your environment
  before the step is meaningful

## Known caveats — read before treating results as a DUT verdict

1. **Thor's QSFP defaults to 10GbE and requires a reflash to reach 25GbE.**
   There is no runtime-only way to enable it — Step 0 in `STEPS.md` is a
   hard precondition, not just a sanity check.
2. **Thor's own 25G software path has a known throughput ceiling.** Multiple
   NVIDIA developer-forum reports (as recent as late 2025) show all 4 MGBE
   lanes correctly negotiating 25G but real throughput capping around
   ~10–17 Gbps per lane, not the ~23–24 Gbps you'd expect — acknowledged by
   NVIDIA as an open issue on their side. **If Step 4 (iperf3 stress test)
   plateaus in that range, do not attribute it to the Avant-X FPGA.** Only
   treat link-down, non-zero/incrementing CRC or frame-error counters
   (Step 3), or throughput well below ~10 Gbps as evidence about the DUT.
3. **A duplicate-MAC firmware bug has been reported on `mgbe1_0`/`mgbe2_0`**
   on some Thor builds, which can make one leg behave differently from the
   others for reasons unrelated to the DUT. Worth a quick check
   (`ip -s -a addr`) if one leg is an outlier.
4. **MACsec being enabled on the MGBE blocks has been linked to
   `mgbe_payload_cs_err` counter increments and MTU getting clamped** —
   worth checking for that counter name specifically in Step 3 if MTU/CRC
   behavior looks odd.

## Open items to confirm for your specific setup

| # | Item | Blocks | Status |
|---|------|--------|--------|
| 1 | Is Thor's QSFP already reflashed for 25GbE (`ODMDATA` / DTB patched), or still default 10GbE? | Step 0 | ✅ Confirmed 25GbE — see `DEBUG_LOG.md`, 2026-07-20 session (`ethtool mgbe0_0` → `Speed: 25000Mb/s`) |
| 2 | Which physical SFP28 leg(s) of the breakout cable are actually connected to the Avant-X board? | Step 1 | ❌ Open — see `DEBUG_LOG.md`, 2026-07-20 session saw 3-of-4 legs with carrier, opposite of the expected single-leg pattern |
| 3 | JetPack/Jetson Linux version on this Thor unit (tuning commands differ slightly by release) | Step 4 | ❌ Open |
| 4 | Do you have `sudo`/SSH access to this Thor unit, or does someone else operate it? | All steps | ❌ Open |

Fill these in (and record who/when) once confirmed, same provenance-tracking
spirit as `../../drafts/fpga_ingress_automation/QUESTIONS.md`.
