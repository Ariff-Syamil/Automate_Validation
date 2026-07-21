# TC-FPGA-006 — Firmware Payload Check

**Component:** RISC-V Firmware &nbsp;·&nbsp; **Priority:** P0 &nbsp;·&nbsp; **Severity:** Critical &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-230
**Run immediately after:** `TC-FPGA-003`, `TC-FPGA-004`, `TC-FPGA-005` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Safety note:** this is a Critical-severity case — follow your bench's standard safety procedure (clear boundary, E-stop armed, etc.) before starting.

**Precondition:** Ethernet and SGDMA dependencies passed; RISC-V firmware image is loaded with payload validation logging enabled.

1. Load the RISC-V firmware image with payload validation logging enabled.
2. Configure SGDMA and memory regions for the deterministic validation payload.
3. Trigger DMA transfer and allow firmware to read the captured payload.
4. Compare firmware-reported payload bytes/checksum against the expected pattern.
5. Verify firmware logs contain pass/fail status and no bus/cache errors.

**Record as PASS if:** Firmware reads the SGDMA payload, reports the expected pattern or checksum, and logs a deterministic pass result without bus or cache errors.
**Record as FAIL if:** Firmware cannot read the payload, data mismatches, checksum fails, logging is absent, or bus/cache errors are reported.
**If it fails:** Add firmware logging around DMA descriptors, cache maintenance, memory barriers, and payload comparison.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-FPGA-006
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/holoscan_fpga/TC-FPGA-006.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-230
```

## Path to Automation

Current state: `automation_readiness` Automatable, `automation_status` In Progress.

**Open Questions:**

1. Does a draft pytest already exist for RISC-V Firmware (check `tests/` and this case's `observations` field), and if so, what's failing or missing to make it pass reliably in CI?
2. What mock/fixture data does this case need (sample frames, config files, golden vectors) that isn't committed yet?
3. Does it depend on real hardware state at all, or can it run fully headless in CI once the fixture/mocks exist?

**Implementation steps once answered:**

1. Add or finish the pytest module under the matching `tests/test_suite_*/` folder, following the structure of an existing passing suite in the same area.
2. Commit any missing fixture data referenced by the test.
3. Run `pytest` locally, confirm it's green, then flip `automation_status` to `Ready`.
