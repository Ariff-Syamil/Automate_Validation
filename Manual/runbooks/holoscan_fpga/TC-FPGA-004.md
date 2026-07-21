# TC-FPGA-004 — 25G Ethernet Link Bring-Up

**Component:** Ethernet MAC/PCS (25G) &nbsp;·&nbsp; **Priority:** P1 &nbsp;·&nbsp; **Severity:** Major &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-229
**Run immediately after:** `TC-FPGA-003` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

This case already has a full hands-on runbook grounded in real Jetson AGX Thor documentation — see [../thor_25g_link_validation/STEPS.md](../thor_25g_link_validation/STEPS.md) (and [../thor_25g_link_validation/README.md](../thor_25g_link_validation/README.md) for context/caveats) rather than duplicating it here.

## Path to Automation

Current state: `automation_readiness` Semi-Automatable, `automation_status` In Progress.

A manual procedure already exists and is grounded in real NVIDIA Jetson AGX Thor documentation/forum reports — see [../thor_25g_link_validation/README.md](../thor_25g_link_validation/README.md).

**Open Questions:**

1. Is Thor's QSFP already reflashed for 25GbE (`ODMDATA` / DTB patched), or still default 10GbE?
2. Which physical SFP28 leg(s) of the breakout cable are actually connected to the Avant-X board?
3. JetPack/Jetson Linux version on this Thor unit (tuning commands differ slightly by release)?
4. Do you have `sudo`/SSH access to this Thor unit, or does someone else operate it?
5. Is there a scriptable way to capture `ethtool` / `tcpdump` / counter output over SSH so Steps 0-3 of the runbook could run unattended, leaving only Step 4's throughput judgement call to a human?

**Implementation steps once answered:**

1. Confirm the open items above with whoever owns this Thor unit (see the "Open items to confirm" table in `Manual/thor_25g_link_validation/README.md`).
2. Wrap the `ethtool` / `tcpdump` / `ethtool -S` commands from `Manual/thor_25g_link_validation/STEPS.md` in an SSH-driven script (e.g. paramiko/fabric) that parses `Speed:` / `Link detected:` / counters instead of requiring a human to read terminal output.
3. Keep the `iperf3` throughput step (Step 4) as a human judgement call, per the known Thor software-path throughput ceiling caveat, unless a numeric pass band is agreed with the FPGA owner.
4. Land the script under `automation/fpga/` + `tests/test_suite_fpga/`, and flip `automation_status` to `Ready` only once verified against real hardware.
