# Manual — Run Priority & Manual Test Procedures

This folder is the home for **manually-executed test cases** across the whole
`automate_5` database, and for the run-priority policy that ties them
together with the cases that already have automation scripts.

## The run policy

1. **Phase 1 — Automated.** Run every test case with `automation_status:
   Ready` first (via `pytest`, `run.bat validate`, or the GUI's Run Test
   action). These have a working script, so there's no manual procedure to
   look up.
2. **Phase 2 — Manual.** Everything else (`automation_status: In Progress`
   or `Not Ready`) still needs a human to execute it. Work through these
   **in the exact order listed** — a case that depends on another one is
   always placed immediately after it, with nothing else run in between, so
   it's obvious the dependency just passed and the environment is still in
   the right state for the next case.

See **[PRIORITY.md](PRIORITY.md)** for the full, generated checklist
covering all 142 test cases in `automate_5/` (97 automated, 41 manual, 4
blocked).

## Regenerating `PRIORITY.md`

`PRIORITY.md` is generated from the live `automate_5/*/test_cases.yaml`
files — don't hand-edit it, regenerate it instead whenever a test case's
`automation_status`, `dependency`, or `steps` change:

```bash
python scripts/manage_tests.py priority automate_5 -o Manual/PRIORITY.md
```

## Detailed runbooks

Most manual cases only have the short `steps:` list already stored in
`test_cases.yaml` (which `PRIORITY.md` pulls in automatically). A few cases
get a full hands-on runbook here instead, when the short steps aren't
enough to execute the case without extra context:

- **[thor_25g_link_validation/](thor_25g_link_validation/)** — full runbook
  for `TC-FPGA-004` (*25G Ethernet Link Bring-Up*), run by hand on the
  Jetson AGX Thor host. See
  [thor_25g_link_validation/README.md](thor_25g_link_validation/README.md)
  for context and
  [thor_25g_link_validation/STEPS.md](thor_25g_link_validation/STEPS.md)
  for the step-by-step procedure. `PRIORITY.md` links out to this instead
  of duplicating it.

To add another one: create a new subfolder here, write its runbook, then
add an entry to `RUNBOOK_LINKS` in
[scripts/manage_tests.py](../scripts/manage_tests.py) so the generated
priority doc links to it instead of showing just the short steps.

## Blocked test cases

`TC-FPGA-010`–`TC-FPGA-013` have neither a working automation script nor a
written manual procedure — they're proposed automation, tracked as
pseudo-code in [../drafts/fpga_ingress_automation/](../drafts/fpga_ingress_automation/)
(not a manual runbook, so it stays out of this folder). `PRIORITY.md` lists
them separately at the bottom instead of putting them in the ordered
checklist, since there's nothing runnable yet.
