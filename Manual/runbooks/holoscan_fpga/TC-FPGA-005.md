# TC-FPGA-005 — Loopback DMA Capture

**Component:** Ethernet RX / SGDMA &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-230
**Run immediately after:** `TC-FPGA-003`, `TC-FPGA-004` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** TC-FPGA-003 and TC-FPGA-004 passed; PCS loopback mode and SGDMA buffer region are configured.

1. Confirm 10G/25G Ethernet dependencies have passed on the current bitstream.
2. Enable PCS loopback mode for the receive path.
3. Transmit a deterministic payload sequence through the loopback path.
4. Trigger SGDMA capture into the configured memory buffer.
5. Read back the buffer and compare payload bytes, length, ordering, and descriptor status.

**Record as PASS if:** SGDMA writes the full deterministic payload into memory with correct byte order, length, ordering, and successful descriptor completion.
**Record as FAIL if:** Payload is missing, truncated, reordered, corrupted, written to the wrong buffer, or descriptor/error status indicates DMA failure.
**If it fails:** Debug SGDMA descriptors, buffer alignment, AXI path, cache coherency, and PCS loopback configuration.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-FPGA-005
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/holoscan_fpga/TC-FPGA-005.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-230
```

## Path to Automation

Current state: `automation_readiness` Automatable, `automation_status` In Progress.

**Open Questions:**

1. Is there already a draft script/fixture for Ethernet RX / SGDMA, and if so, what's blocking it from a verified passing run on real hardware?
2. What's the exact pass/fail measurement source (counter, register, log) for this case, and is it already machine-readable?
3. Is there a safe way to run this repeatedly without a human present, or does hardware setup (cabling, bitstream load, power-on) require a human step every time?

**Implementation steps once answered:**

1. Confirm the open questions above with this case's owner.
2. Script the setup/measurement/pass-fail logic under a `tests/test_suite_*/` module, following the fixture patterns already used in `tests/test_suite_backend/`.
3. Run it once against real hardware, record the result in `automate_5/runs.yaml`, and flip `automation_status` to `Ready` only after that passes.
