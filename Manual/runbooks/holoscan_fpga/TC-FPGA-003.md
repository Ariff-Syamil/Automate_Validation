# TC-FPGA-003 — 10G Ethernet Link Stability

**Component:** Ethernet MAC/PCS &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-229
**Dependency:** None.

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** FPGA image with 10G Ethernet MAC/PCS is loaded; link partner and traffic generator are configured.

1. Load the FPGA image containing the 10G Ethernet MAC/PCS design.
2. Connect the configured 10G link partner or traffic generator.
3. Bring the link up and confirm negotiated speed and link status.
4. Send sustained bidirectional traffic at the nominal validation rate.
5. Monitor link flaps, packet loss, CRC errors, and throughput counters.

**Record as PASS if:** 10G link remains up for the validation interval, throughput meets target rate, packet loss is zero, and CRC/error counters do not increase.
**Record as FAIL if:** Link fails to come up, flaps during traffic, throughput is below target, packets are lost, or CRC/error counters increase.
**If it fails:** Inspect PCS status, clocking, cable/SFP, link partner configuration, and signal-integrity counters.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-FPGA-003
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/holoscan_fpga/TC-FPGA-003.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-229
```

## Path to Automation

Current state: `automation_readiness` Automatable, `automation_status` In Progress.

**Open Questions:**

1. Is there already a draft script/fixture for Ethernet MAC/PCS, and if so, what's blocking it from a verified passing run on real hardware?
2. What's the exact pass/fail measurement source (counter, register, log) for this case, and is it already machine-readable?
3. Is there a safe way to run this repeatedly without a human present, or does hardware setup (cabling, bitstream load, power-on) require a human step every time?

**Implementation steps once answered:**

1. Confirm the open questions above with this case's owner.
2. Script the setup/measurement/pass-fail logic under a `tests/test_suite_*/` module, following the fixture patterns already used in `tests/test_suite_backend/`.
3. Run it once against real hardware, record the result in `automate_5/runs.yaml`, and flip `automation_status` to `Ready` only after that passes.
