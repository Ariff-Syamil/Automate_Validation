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
covering all 142 test cases in `automate_5/` (97 automated, 45 manual).
Every manual case links out to its own runbook (below) instead of showing
just the short `steps:` list inline.

## Regenerating `PRIORITY.md` and the runbooks

Both `PRIORITY.md` and every file under `runbooks/` are generated from the
live `automate_5/*/test_cases.yaml` files — don't hand-edit them, regenerate
instead whenever a test case's `automation_status`, `dependency`, `steps`,
or other fields change:

```bash
python scripts/manage_tests.py priority automate_5 -o Manual/PRIORITY.md --write-runbooks Manual/runbooks
```

(`run.bat priority` currently only regenerates `PRIORITY.md` — pass
`--write-runbooks` explicitly, as above, to also refresh the runbook files.)

## `runbooks/` — one file per manual test case

**[runbooks/](runbooks/)** has one Markdown file per non-`Ready` test case,
mirroring the `automate_5/<subcomponent>/` layout:
`runbooks/<subcomponent>/<TC-ID>.md` (e.g. `runbooks/mechanical/TC-HW-01.md`).
Each file has:

1. **Header** — component, priority, severity, Jira link, and dependency
   info (including the same "run immediately after" callout used in
   `PRIORITY.md`).
2. **Manual Procedure** — precondition, numbered steps, pass/fail criteria,
   and a `runs.yaml` snippet to record the result. Expanded straight from
   that case's own `test_cases.yaml` fields.
3. **Path to Automation** *(only for `automation_status: In Progress`
   cases, plus the four `TC-FPGA-010`–`013` ingress cases)* — current
   automation state, **Open Questions**, and **Implementation steps** for
   finishing the script. Most of these are templated from the case's
   `test_environment_ci_hil` + `automation_readiness`, since there's no
   independent domain research behind them; `TC-FPGA-004` and
   `TC-FPGA-010`–`013` instead draw on real research already in the repo
   (see below).

Two cases keep their content elsewhere instead of duplicating it:

- **`TC-FPGA-004`** — its Manual Procedure lives at
  **[thor_25g_link_validation/](thor_25g_link_validation/)**
  ([README](thor_25g_link_validation/README.md) for context,
  [STEPS.md](thor_25g_link_validation/STEPS.md) for the procedure), run by
  hand on the Jetson AGX Thor host.
  `runbooks/holoscan_fpga/TC-FPGA-004.md` only carries its "Path to
  Automation" section and links back here.
- **`TC-FPGA-010`–`013`** — their "Path to Automation" sections draw on the
  real open questions and pseudo-code already tracked in
  [../drafts/fpga_ingress_automation/](../drafts/fpga_ingress_automation/).

To point a case at an existing runbook elsewhere instead of the generated
`runbooks/<sub>/<TC-ID>.md` location (like `TC-FPGA-004` above), add an
entry to `RUNBOOK_LINKS` in
[scripts/manage_tests.py](../scripts/manage_tests.py). `scripts/gui.py`
keeps its own small mirrored copy of `RUNBOOK_LINKS` (used by the
`ManualResultDialog` operators see while recording a manual result, to
pull in that case's "Manual Procedure" excerpt) — update both dicts
together so the GUI and the generated docs stay pointed at the same file.
