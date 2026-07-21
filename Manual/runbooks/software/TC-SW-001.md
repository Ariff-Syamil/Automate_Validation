# TC-SW-001 — UDP Packet Round Trip

**Component:** UDP Communication &nbsp;·&nbsp; **Priority:** P1 &nbsp;·&nbsp; **Severity:** Major &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-224
**Run immediately after:** `TC-FPGA-003`, `TC-FPGA-004` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Precondition:** 10G/25G FPGA Ethernet dependencies are available; host UDP listener port is open; packet format is agreed with FPGA sender.

1. Start the host UDP listener on the configured validation port.
2. Transmit a known payload from the FPGA sender through the validated Ethernet path.
3. Capture the received packet bytes and metadata on the host.
4. Compare payload, sequence number, and length against the expected packet contract.
5. Repeat for a short burst to verify no drops under nominal rate.

**Record as PASS if:** Every transmitted UDP packet is received once, with intact payload bytes, expected sequence order, and no malformed length or checksum indicators.
**Record as FAIL if:** Any packet is lost, duplicated, malformed, received out of order, or rejected by the host listener.
**If it fails:** Check FPGA sender counters, host MTU, socket buffers, firewall rules, and packet capture for loss or corruption.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-SW-001
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/software/TC-SW-001.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-224
```

## Path to Automation

Current state: `automation_readiness` Automatable, `automation_status` In Progress.

**Open Questions:**

1. Does a draft pytest already exist for UDP Communication (check `tests/` and this case's `observations` field), and if so, what's failing or missing to make it pass reliably in CI?
2. What mock/fixture data does this case need (sample frames, config files, golden vectors) that isn't committed yet?
3. Does it depend on real hardware state at all, or can it run fully headless in CI once the fixture/mocks exist?

**Implementation steps once answered:**

1. Add or finish the pytest module under the matching `tests/test_suite_*/` folder, following the structure of an existing passing suite in the same area.
2. Commit any missing fixture data referenced by the test.
3. Run `pytest` locally, confirm it's green, then flip `automation_status` to `Ready`.
