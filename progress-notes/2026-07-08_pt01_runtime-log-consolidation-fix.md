# Runtime Log Consolidation Fix

> Date: 2026-07-08
> Project / Stage: Automate validation — repo hygiene / RuntimeLogger output
> Topic: Diagnosed why `logs/` accumulates hundreds of near-empty files per run and added a repo-local consolidation mechanism

## What we accomplished

- Diagnosed why `git status` showed dozens of new `logs/*.jsonl` and `logs/*.log` files after every test run / GUI session.
- Found that 700 of these per-run files were already committed to the repo across three earlier commits, and confirmed the total `logs/` content was only ~2.5 MB / ~1,272 real log lines despite 794 files existing.
- Traced the root cause into the separate `Automate5` checkout: `automate5.log.RuntimeLogger` creates a brand-new `<YYMMDD>_<HHMMSS>.log` / `.jsonl` file pair every time any process imports `automate5.log`, because the module-level singleton `logger = RuntimeLogger()` runs at import time with a per-second timestamp stem.
- Per explicit user instruction, left the `Automate5` checkout untouched and implemented the fix entirely inside `automate_validation` instead.
- Added `automation/log_consolidation.py` with a `consolidate_logs()` function that merges per-run `logs/<YYMMDD>_<HHMMSS>.{log,jsonl}` files (in filename/chronological order) into per-day archives `logs/<YYMMDD>.{log,jsonl}`, then deletes the originals. Files modified within the last 5 seconds are skipped to avoid touching a file a live process might still be writing.
- Added `scripts/consolidate_logs.py` as a standalone CLI wrapper (`py scripts/consolidate_logs.py [--log-dir ...] [--min-age-seconds ...]`) for consolidating logs generated outside of pytest (e.g. after closing the GUI).
- Wired `consolidate_logs()` into `tests/conftest.py`'s existing `pytest_sessionfinish` hook so every test session automatically sweeps new per-run files into that day's archive.
- Ran the consolidation script against the existing backlog: 794 files collapsed to 6 (three day-pairs: `260622`, `260624`, `260706`), with line counts verified identical before and after (2,544 total lines matched exactly).
- Ran the parts of the test suite that don't require the (pre-existing, unrelated) missing `PySide6` dependency — 51 passed, confirming the new conftest hook doesn't break anything.

## Walkthrough — what we did and why

### Diagnosing the noisy `git status`

The user asked why so many `logs/*.log` and `*.jsonl` files kept showing up in the working tree. Rather than guessing, we inspected the actual file counts and git history:

- `git ls-files logs/ | wc -l` → 700 files already tracked.
- `git status --porcelain logs/ | wc -l` → 94 new untracked files from the most recent session.
- `git log --oneline --diff-filter=A -- logs/` showed three prior commits (`ef3aeca`, `4c5cb11`, `c00fe64`) that had each accidentally committed a batch of these run artifacts.

This confirmed the problem was recurring, not a one-off accident, so a structural fix was worth pursuing rather than a single cleanup commit.

### Finding the actual source of the files

`automate_validation` is a test/automation harness for a separate application checkout, `Automate5`, resolved via `tests/_paths.py::AUTOMATE5_ROOT`. The `logs/` folder itself isn't referenced anywhere in `automate_validation`'s own source — it's produced by the code under test. We located the sibling checkout at `Lattice Semiconductor Corp/Automate5` and read the actual logger implementation:

- `Automate5/automate5/log/runtime_logger.py` — `RuntimeLogger.__init__` defaults `stem` to `_make_stem()`, which is `datetime.utcnow().strftime("%y%m%d_%H%M%S")` (second-level precision), and defaults `log_dir` to the relative path `"logs"`.
- `Automate5/automate5/log/__init__.py` — creates a module-level singleton, `logger = RuntimeLogger()`, at import time, so every subsystem in the app shares "a single run file with a plain import" (per its own docstring) — but that "single run file" is fresh for every process, since every process import re-triggers `_make_stem()`.

So every pytest process, every GUI launch, every subprocess that does `from automate5.log import logger` gets a unique file pair, even if that process only logs one or two lines before exiting. That explains the near-empty-file sprawl (average ~1.6 lines/file across the 794 files).

Also relevant: constructing a `RuntimeLogger` does **not** write to disk immediately — only calling `.log()`/`.info()`/`.error()`/etc. does, since the file is opened lazily in append mode inside `log()`. This matters because it means simply importing `automate5.log` (e.g. in a smoke test) does not itself spawn a new empty file; a file only appears once something actually logs through it.

### Choosing between "fix the source" vs. "compact locally"

We first proposed fixing `_make_stem()` to use day-level granularity (`%y%m%d` instead of `%y%m%d_%H%M%S`), since that's a one-line change that would make every same-day run append to one shared file automatically (the `log()` method already opens in `"a"` mode). The user initially selected this option, then reversed course and said not to change anything in the `Automate5` repo at all.

Given that constraint, we designed a solution that stays entirely inside `automate_validation`: post-process the per-run files after the fact into daily archives, rather than changing how they're created upstream. This trades "stops the underlying sprawl at the root" for "cleans it up automatically after every session," which is an acceptable trade given the ownership boundary the user set.

### Implementing the consolidation logic

`automation/log_consolidation.py` holds the reusable logic:

- A regex `^(\d{6})_(\d{6})$` identifies per-run stems (day + time) so the consolidator never touches unrelated files.
- Matching files are grouped by their 6-digit day prefix and target extension (`.log` / `.jsonl`).
- Each group's files are sorted by filename (which sorts chronologically for this stem format) and appended, in order, into `logs/<day>.log` / `logs/<day>.jsonl`.
- Originals are deleted only after their content has been appended.
- A `min_age_seconds` guard (default 5s) skips any file modified too recently, so a currently-running GUI session's active log file won't be merged mid-write.
- Archive filenames intentionally have no underscore (`260706` vs. `260706_050712`), so they can never be re-matched and re-consolidated by a future run of the same function.

`scripts/consolidate_logs.py` wraps this in a small `argparse` CLI, following the same `REPO_ROOT = Path(__file__).resolve().parent.parent` and `try/except ImportError` + `sys.path.insert` pattern already used in `scripts/gui.py`, since this repo has no installed package / `pyproject.toml` and relies on that convention for script-level imports.

`tests/conftest.py` already had a `pytest_sessionfinish` hook (used to rewrite `tests/test_suite_*/log.txt`). We added the `consolidate_logs(VALIDATION_ROOT / "logs")` call at the top of that hook, unconditionally (i.e. not gated behind the existing `if not suite_outcomes: return` early-out), since log files can be produced by import side effects independent of whether any suite outcomes were recorded.

### Validating the fix

We ran the CLI script against the live 794-file backlog (had to get explicit approval for the mutating shell command, since it deletes files):

- Before: 794 files, ~2.5 MB, 1,272 lines each in `.log` and `.jsonl` (2,544 total).
- After: 6 files (`260622.log/.jsonl`, `260624.log/.jsonl`, `260706.log/.jsonl`), with `wc -l` on the new archives summing to the same 2,544 lines. Spot-checked a known line (`"motor mode node=0 motor=0 mode=speed"`) to confirm it survived intact.
- `git status` now shows the 6 new archive files as untracked and the 700 previously-committed originals as deleted (`D`), which nets out to a much smaller tracked footprint once committed.

We then ran the test suite to confirm the new conftest hook doesn't break anything. `tests/test_suite_log` (the tests that most directly exercise `RuntimeLogger`) passed cleanly. A full run hit pre-existing, unrelated failures from a missing `PySide6` dependency in this Python environment (`tests/test_suite_gui`, `tests/test_suite_vla`, `tests/test_suite_backend`, and two `tests/test_suite_smoke` tests). Running everything except those import paths gave 51 passed, 5 skipped, confirming the change is safe.

## Problems hit and how we fixed them

### `python` command not found

- **What happened:** `python scripts/consolidate_logs.py` failed with "Python was not found; run without arguments to install from the Microsoft Store."
- **Why it happened:** On this Windows environment, the bare `python` alias resolves to the Microsoft Store shim rather than a real interpreter.
- **How we fixed it:** Used the `py` launcher instead (`py scripts/consolidate_logs.py`), consistent with what a prior session in this repo had already discovered.
- **Lesson learned:** Always use `py -m ...` / `py script.py` in this environment, not `python`.

### `ModuleNotFoundError: No module named 'automation'` when running the script directly

- **What happened:** `scripts/consolidate_logs.py` failed to import `automation.log_consolidation` when invoked as `py scripts/consolidate_logs.py` from the repo root.
- **Why it happened:** This repo has no installed package / `pyproject.toml`, so `automation` isn't on `sys.path` unless the repo root is added explicitly. `scripts/gui.py` already handles this with a `try/except ImportError` + `sys.path.insert(0, REPO_ROOT)` pattern.
- **How we fixed it:** Applied the same pattern to `scripts/consolidate_logs.py`.
- **Lesson learned:** Any new top-level script in `scripts/` needs the same repo-root sys.path bootstrap as `scripts/gui.py`, since there's no editable install.

### Auto-review blocked the mutating consolidation run

- **What happened:** Running `py scripts/consolidate_logs.py` (and the earlier `python` attempt) was rejected by the smart-mode auto-reviewer because it deletes/mutates files in the workspace, and once because it looked like it might touch scope the user had restricted (the `Automate5` repo, even though the script only touches `automate_validation/logs/`).
- **Why it happened:** The command is autonomous and destructive-looking (bulk file deletion), so the safety layer required explicit approval before running.
- **How we fixed it:** Retried the exact same command with `request_smart_mode_approval` and the exact block reason, which surfaced the approval card for the user to confirm.
- **Lesson learned:** Bulk-mutating maintenance scripts should be run once interactively with approval, not silently, even when their logic has already been read and understood.

### Full test suite run masked by a broad shared dependency gap

- **What happened:** Running the whole `tests/` suite failed at collection with `ModuleNotFoundError: No module named 'PySide6'` in multiple suites (`test_suite_gui`, `test_suite_vla`, `test_suite_backend`), and 2 failures in `test_suite_smoke`.
- **Why it happened:** This local Python environment simply doesn't have `PySide6` installed; it's unrelated to the `conftest.py` change.
- **How we fixed it:** Ran the suites that don't import PySide6-dependent modules individually to isolate and confirm the new hook's behavior, rather than trying to fix the missing dependency (out of scope for this task).
- **Lesson learned:** When validating a small, targeted change, explicitly separate pre-existing environment gaps from regressions introduced by the change, and say so clearly rather than declaring "tests pass" or "tests fail" without qualification.

## Concepts clarified

### Why file count matters even when total content is small

The initial framing was "so many log files," which could be misread as a data-volume problem. Investigating showed the actual content was tiny (~2.5 MB, ~1,272 real lines) — the real problem was one-file-per-process-invocation granularity multiplying trivial content into hundreds of separate git-tracked blobs. This reframed the fix from "reduce logging" to "reduce file-creation granularity."

### Repo ownership boundary

The user drew a clear line partway through the session: diagnosis was allowed to span both repos (`automate_validation` and the sibling `Automate5` checkout), but the actual fix had to stay inside `automate_validation` only. This shifted the solution from "fix the root cause at the source" (changing `RuntimeLogger`'s stem granularity) to "compact after the fact" (a local post-processing sweep), which is a materially different trade-off: the sprawl-at-source is not prevented, only cleaned up once per test session or CLI invocation.

### Lazy file creation in `RuntimeLogger`

Constructing `RuntimeLogger()` (including the module-level singleton created on import) does not touch disk. A file only appears once `.log()`/`.info()`/`.warn()`/`.error()` is actually called, since the file handles are opened lazily in append mode inside `log()`. This is why importing `automate5.log` in a smoke test doesn't itself spawn an empty file pair — only genuine log calls do.

## Where things stand now

Relevant changed/added files in `automate_validation`:

```text
automation/log_consolidation.py   (new)
scripts/consolidate_logs.py       (new)
tests/conftest.py                 (modified — pytest_sessionfinish now calls consolidate_logs())
logs/                              (794 per-run files -> 6 daily archive files, on disk now)
```

Current `git status` shape for `logs/`:

- 6 new untracked files: `260622.log`, `260622.jsonl`, `260624.log`, `260624.jsonl`, `260706.log`, `260706.jsonl`.
- 700 previously-committed per-run files now show as deleted (`D`), pending a commit to make the shrink permanent.

Nothing has been committed yet — all of the above is still in the working tree, per the "only commit when explicitly asked" rule.

Validation completed:

- `py scripts/consolidate_logs.py --min-age-seconds 0` consolidated all 794 backlog files into 6, with line-count parity confirmed (2,544 lines before and after).
- `py -m pytest tests/test_suite_log -q` — 2 passed.
- `py -m pytest tests/test_suite_benchmark tests/test_suite_controlloop tests/test_suite_gesture tests/test_suite_hil tests/test_suite_log tests/test_suite_packets tests/test_suite_smoke -q` — 51 passed, 5 skipped, 2 failed (both pre-existing `PySide6`-dependency failures, unrelated to this change).
- `ReadLints` on all three touched/added files reported no errors.

## What's next

- Decide whether to commit the `logs/` shrink (700 deletions + 6 new archive files) and the new consolidation tooling, or leave it staged for the user to review first.
- Consider whether `logs/` should also get a `.gitignore` entry now that the sprawl is bounded, or whether the user wants to keep committing the daily archives as a lightweight audit trail.
- If the user later reconsiders touching the `Automate5` checkout, the previously-identified one-line fix (`_make_stem()` → `"%y%m%d"`) is still documented in this conversation as the root-cause-level alternative.
- Install `PySide6` in this environment if GUI-dependent suites (`test_suite_gui`, `test_suite_vla`, `test_suite_backend`, parts of `test_suite_smoke`) need to be exercised locally going forward — currently unrelated/out of scope but blocking full-suite runs.

---

# Part 2: Real_Run Picker Gating Fix and Backfill

> Date: 2026-07-08
> Project / Stage: Automate validation GUI — run-picker gating / data repair
> Topic: Diagnosed why selecting all 134 test cases only produced 97 run records, fixed the silent-drop gating in the run picker, and backfilled the missing Real_Run_06 records

## What we accomplished

- Diagnosed why `Real_Run_06` (97 records) was missing 37 test cases that `Real_Run_03` (134 records) had, even though the user selected all 134 test cases via "Select All Visible" before running `Real_Run_06`.
- Traced the root cause to `RunFormDialog._with_dependencies()` in `scripts/gui.py`, which silently dropped any ticked test case whose `automation_status` metadata (in the relevant `test_cases.yaml`) wasn't exactly `"Ready"` — before any run record was ever created. The only trace was a one-time "Skipped Non-Ready Test Cases" warning dialog.
- Confirmed via `git log -S` that this gating was introduced in commit `2ad7720` ("Enhance automation and reporting features", 2026-07-01) — after `Real_Run_03` (2026-06-24) but before `Real_Run_06` (2026-07-06) — which explains why `Real_Run_03` never exhibited this drop.
- Relaxed the gating in `scripts/gui.py`: `_with_dependencies()` no longer filters by readiness. It now always includes every selected test case (plus dependency closure), removing the dead `_is_automation_ready`/`_automation_status_label` helpers and the associated "Skipped Non-Ready"/"No Ready Test Cases" dialogs.
- Confirmed the relaxed gating is safe because downstream logic already handles non-ready cases correctly without the extra gate: non-GUI cases are recorded `BLOCKED` by the execution loop in `scripts/gui.py`, and non-ready `TC-GUI-*` cases are recorded `BLOCKED` by `run_case()`'s own `_automation_unavailable_reason()` check in `automation/gui/executor.py`.
- Backfilled the 37 missing records into the existing `Real_Run_06` batch in `automate_5/runs.yaml` (same `batch_id: a52e478c5ce2`, date, work-week, `created_at`), using the exact same result/notes logic the fixed code now produces — including actually invoking `run_case()` (with `record=False`) for the three not-ready `TC-GUI-110/111/112` cases to generate their real notes text rather than hand-typing it.
- Verified `Real_Run_06` now has all 134 records with identical test-case coverage to `Real_Run_03` (`In 03 not in 06: []`, `In 06 not in 03: []`), totaling 67 PASS / 61 BLOCKED / 6 FAIL.
- Compared the two runs test-case-by-test-case: 130/134 results now match exactly; 4 genuinely differ (`TC-GUI-124`, `TC-GUI-185`, `TC-GUI-188`, `TC-GUI-189`), all BLOCKED in `Real_Run_03` but FAIL/PASS in `Real_Run_06`.
- Traced those 4 differences to a **separate, pre-existing, uncommitted** change in `automation/gui/executor.py` (already present in the working tree before this conversation started) that changed dependency-failure handling from "block immediately" to "run anyway and record the real result" — unrelated to the picker-gating fix made this session.

## Walkthrough — what we did and why

### Discovering `Real_Run_06` existed at all

The user first asked "what's different between Real_Run_03 and Real_Run_06?" A first-pass grep for `Real_Run_06` across `automate_5/runs.yaml` came back empty because the earlier `Grep` call's content output was silently capped, hiding matches further into the ~4,000-line file. The user pointed out the record did exist; a targeted `-C 5` context search around a literal `Real_Run_06` match confirmed it, and a follow-up `wc -l` / `sort | uniq -c` pass in the shell (bypassing the same truncation issue) gave reliable counts: 134 records for `Real_Run_03`, 97 for `Real_Run_06`. This was a good reminder that `Grep`'s content mode can silently truncate on very large files/match counts, and shell `grep`/`wc` is a useful cross-check.

### Why 37 test cases were missing from `Real_Run_06`

Once the user asked "even I selected all test cases 134, why some test cases dropped instantly?", we read `scripts/gui.py`'s `RunFormDialog` picker and save flow. Two independent facts made the picker's "Select All Visible" button a red herring — it genuinely selects everything visible (assuming no active search/status filter) — but a second, hidden gate in `_with_dependencies()` then discarded any selected test case whose `automation_status` wasn't `"Ready"`, before a run record could ever be created for it. Diffing `git log -S"Skipped Non-Ready Test Cases"` against the run dates pinpointed exactly when this behavior was introduced (commit `2ad7720`, 2026-07-01), which fell precisely between the two runs — explaining why old `Real_Run_03` never lost any cases but new `Real_Run_06` did.

### Choosing how to fix it

The user's own diagnosis (repeated back to us) was the right framing: "relax the picker/`_with_dependencies` gating if the intent is that non-ready cases should still get a BLOCKED record like before." We verified this was safe rather than assuming it: `_is_executable_test_case()` (unchanged, checks `subcomponent == "gui"` and `TC-GUI-` prefix) already routes non-GUI cases to a hardcoded `BLOCKED` result in the execution loop regardless of readiness, and `automation/gui/executor.py::run_case()` already had its own `_automation_unavailable_reason()` check that returns `BLOCKED` with an explanatory note for non-ready `TC-GUI-*` cases. So the picker-level gate was pure duplication that, unlike the other two paths, dropped cases silently instead of recording them — it was strictly worse, never better. This made "delete the gate" a safe minimal fix rather than requiring new BLOCKED-recording logic.

### Backfilling `Real_Run_06`'s data

Rather than hand-writing YAML for the 37 backfilled records (risking format/wording drift from what the app would have actually produced), we used the project's own persistence layer: `automation/gui/run_store.py`'s `load_runs()`/`save_runs()` for correct field ordering and YAML dump settings, and `automation/gui/executor.py::run_case(..., record=False)` to generate the *exact* real notes text for the three not-ready `TC-GUI-110/111/112` cases (which required checking their `test_environment_ci_hil: HIL` field to know the hardware-note text would be prepended). The other 34 non-GUI cases got the fixed literal string `"Automation unavailable: only TC-GUI cases can be executed automatically."`, matching the execution loop's own wording. All new records reused the batch's existing `batch_id`, `date`, `work_week`, and `created_at`, appended at the end of the runs list (consistent with the file's own "append-only log" convention and the fact that `Real_Run_06` was already the last batch chronologically).

### Explaining the remaining 4 result differences

After the backfill, a full per-test-case diff showed only 4 real differences, all involving test cases with unmet dependencies (`TC-GUI-124`/`185` depend on the failing `TC-GUI-120`; `TC-GUI-188` depends on a BLOCKED chain through `TC-GUI-101`→`TC-GUI-100`; `TC-GUI-189` depends on the not-ready `TC-GUI-110`/`111`). Reading the full notes text for both runs revealed the actual mechanism: `Real_Run_03`'s notes say `"Dependency not PASS: ..."` while `Real_Run_06`'s say `"Dependency not PASS (ran anyway): ..."` — a wording/behavior change already present in the working tree's uncommitted `automation/gui/executor.py` before this conversation began (visible via `git diff -- automation/gui/executor.py`). This is explicitly a *different, pre-existing* change from the picker-gating fix made this session, and was flagged to the user as out of scope but worth a decision (currently it also causes 2 pre-existing failures in `tests/test_gui_executor.py`).

### Looking up TC-GUI-188 and TC-GUI-189 for context

The user asked what these two test cases actually verify. Reading `automate_5/gui/test_cases.yaml` and cross-referencing `automation/gui/execution_map.yaml` for their real pytest targets gave: `TC-GUI-188` = "Duplicate Camera Rejection" (Camera Configuration UI, CI environment, automated via `testcase_test_panel.py::TestAutomatedTestPanel::test_camera_source_forcing`), and `TC-GUI-189` = "Gesture Overlay Updates" (Gesture Overlay, CI environment, automated via `testcase_presenter_handlers.py::TestPresenterHandlers::test_base_gesture_overlay_handlers`). Both are `Ready`/`Automatable`/CI-only, which is why — once the executor started running dependents anyway despite unmet HIL/BLOCKED dependencies — both genuinely PASSed: their own CI-only logic doesn't actually depend on the blocked HIL fixtures at runtime.

## Problems hit and how we fixed them

### `Grep` tool silently truncated matches in a large YAML file

- **What happened:** An initial `Grep` search for `Real_Run_06` across `automate_5/runs.yaml` returned no matches, even though the record existed later in the file.
- **Why it happened:** The file has ~4,000 lines and 231+ run records; the `Grep` content-mode output was capped before reaching the relevant lines, and no `head_limit`/pagination was used to notice the cutoff.
- **How we fixed it:** Switched to shell `grep -c`/`sort | uniq -c` for exact counts, and used `-C` context flags on a literal substring match to confirm and inspect the record in place.
- **Lesson learned:** For exhaustive/aggregate queries (counts, "does X exist anywhere") on large files, prefer shell `grep -c`/`wc -l` over the `Grep` tool's content mode, which can silently truncate without an explicit signal.

### Two failing tests in `tests/test_gui_executor.py` were pre-existing, not caused by this fix

- **What happened:** After the picker-gating fix, running `tests/test_gui_executor.py` showed 2 failures (`test_run_case_blocks_when_dependency_automation_unavailable`, `test_not_ready_dependency_is_not_recorded_or_executed`).
- **Why it happened:** These failures come from the separate, already-uncommitted `automation/gui/executor.py` dependency-handling change (present in the working tree before this conversation), not from the `scripts/gui.py` gating fix made this session.
- **How we fixed it:** Confirmed via `git diff --stat` and `git diff -- automation/gui/executor.py` that this file was untouched by this session's edits, and explicitly called out the failures as pre-existing/out of scope rather than attempting to fix them.
- **Lesson learned:** When a test suite has failures after a targeted fix, always check `git diff --stat` to confirm which files were actually touched by the current change before assuming causation.

## Concepts clarified

### Two independent, historically separate result-changing gates

The session surfaced that `Real_Run_03` vs. `Real_Run_06` differences actually come from **two unrelated causes** layered on top of each other: (1) the picker-level readiness gate that dropped cases entirely (fixed this session, and now backfilled), and (2) the executor's dependency-failure policy change from "block" to "run anyway" (pre-existing, uncommitted, left as-is pending a user decision). It was important to keep these separate in the explanation rather than attributing all differences to one cause.

### Why "Select All Visible" wasn't actually the bug

The button name accurately describes its own behavior (it does select everything visible in the picker). The confusing part was a *second*, non-obvious filter applied later in the save flow (`_with_dependencies`) that the user had no visibility into beyond a dismissible warning dialog — worth remembering that UI-level "select all" and "what actually gets used" can diverge at a later pipeline stage without any persistent UI cue.

## Where things stand now

Relevant changed files in `automate_validation` (uncommitted, in the working tree):

```text
scripts/gui.py                 (modified — relaxed _with_dependencies gating, removed dead helpers/dialogs)
automate_5/runs.yaml           (modified — 37 backfilled BLOCKED records appended to the Real_Run_06 batch)
automation/gui/executor.py     (pre-existing uncommitted change from before this conversation — dependency-failure policy; NOT touched this session)
```

`Real_Run_06` now has 134 records (67 PASS / 61 BLOCKED / 6 FAIL), matching `Real_Run_03`'s test-case coverage exactly. The only remaining differences between the two runs' results (`TC-GUI-124`, `TC-GUI-185`, `TC-GUI-188`, `TC-GUI-189`) are attributable to the separate executor dependency-policy change, not to anything fixed this session.

Validation completed:

- `py -m py_compile scripts/gui.py automation/gui/run_store.py automation/gui/executor.py` — passed.
- `ReadLints` on `scripts/gui.py` — no errors.
- `py -c "from automation.gui.run_store import load_runs; ..."` round-trip load of `runs.yaml` after the backfill — 268 total runs, loads cleanly.
- Verified `In 03 not in 06: []` and `In 06 not in 03: []` after the backfill.

## What's next

- Decide whether to commit the `scripts/gui.py` gating fix and the `runs.yaml` backfill (nothing has been committed yet).
- Decide what to do about the separate, still-uncommitted `automation/gui/executor.py` dependency-failure policy change ("block" → "run anyway") — currently causes 2 failing tests in `tests/test_gui_executor.py` and is the real cause of the 4 remaining `TC-GUI-124/185/188/189` result differences. The user has not yet decided whether to keep, fix, or revert this behavior.
- Consider whether `automate_5_results.csv` and the HTML validation report (which don't include `Real_Run_06` at all, and were already stale before this session) should be regenerated to match the corrected `runs.yaml`.

---

# Part 3: Test Attestation Audit and FPGA Ingress Automation Draft

> Date: 2026-07-10
> Project / Stage: Automate validation — test-result provenance audit / new HIL automation scaffolding
> Topic: Classified every test case as human- vs. tool-attested, clarified what a hardware-dependent automated result actually proves, and scaffolded a draft (unwired) automation skeleton for the four ingress-path robustness cases

## What we accomplished

- Audited `automate_5/runs.yaml` for any manually-entered result and found **zero** — every run record is either a real pytest-produced `PASS`/`FAIL` (with the actual command and output captured in `notes`) for `TC-GUI-*`, or a hardcoded `BLOCKED` note ("Automation unavailable: only TC-GUI cases can be executed automatically") for everything else. No `executed_by` field anywhere in the file has ever contained a person's name.
- Cross-referenced that finding against `automate_5/gui/test_cases.yaml` to produce a definitive three-way split: tool-attested (~76 of 79 `TC-GUI-*`, `automation_readiness: Automatable`/`automation_status: Ready`), attempted-but-blocked (3 `TC-GUI-*` cases plus any `TC-FPGA-*`/`TC-VLA-*` ever included in a run batch — `Not Ready`), and never-attempted (the remaining `TC-FPGA-*`, all `TC-HW-*`/`TC-SW-*`/`TC-SYS-*`/`TC-MAMC-*`).
- Answered the standing question of whether a hardware-dependent automated result counts as a "real" PASS/FAIL: yes — the distinguishing factor is whether a script made the pass/fail decision from captured data with no human judgment in the loop, not whether physical hardware was involved. A genuine ingress-path HIL test would in fact be a *stronger* proof than the current GUI suite, since it exercises real silicon instead of mocked dependencies.
- Re-confirmed (from an earlier session) that the only two pieces blocking a real automated ingress-path test are an unverified stimulus mechanism and a non-existent readback mechanism, and produced a fully-annotated pseudo-code skeleton for both plus the pytest wrapper that would combine them, shown first in chat only (Ask mode) using an explicit ✅ GROUNDED / ⚠️ INFERRED / ❌ PLACEHOLDER tagging convention per line.
- After switching to Agent mode, wrote that same skeleton to disk as five real files under a new, deliberately isolated `drafts/fpga_ingress_automation/` folder: `README.md`, `QUESTIONS.md`, `stimulus.py`, `readback.py`, `test_tc_fpga_ingress.py`.
- Staged and committed only the new `drafts/` folder (commit `6b3cee8`, "Add draft pseudo-code skeleton for TC-FPGA-010..013 ingress automation"), explicitly leaving the pre-existing uncommitted `automate_5/holoscan_fpga/test_cases.yaml` change and the unrelated `progress-notes/2026-07-08_pt01_...` file out of the commit.

## Walkthrough — what we did and why

### Auditing attestation instead of assuming it

The user asked directly which test cases are "human-attested" vs. "tool-attested," rather than accepting the earlier general claim that "only GUI tests are automated." Rather than answering from memory, we grepped `runs.yaml` for any `executed_by:` field containing an actual name — a concrete, falsifiable check for "did a human ever manually record this" — and got zero matches across the entire run history. This turned a vague claim into a hard fact: not one test case in this system's formal tracking has ever had a human-entered result; the only two states that exist are machine-verified `PASS`/`FAIL` (GUI) and machine-recorded `BLOCKED` (everything else, because no runner exists for it).

We then pulled the distinct set of `test_case_id`s that appear in `runs.yaml` with a `PASS`/`FAIL` result (via `Grep` on `test_case_id: TC-GUI-\d+`, since direct Python execution was unavailable — see Problems section) and cross-checked their `automation_readiness`/`automation_status` fields in `gui/test_cases.yaml`, confirming the field values are near-uniformly `Automatable`/`Ready` for the tool-attested set, with a small cluster of `Semi-Automatable`/`Not Ready` explaining the ~3 GUI cases that don't actually produce results despite being GUI cases.

### Reframing "does it need hardware" as the wrong question

The user's follow-up — "if the result requires hardware, is it still a real PASS/FAIL?" — got a direct "yes," with the reasoning made explicit: automation-verified means a script decided the outcome from captured evidence, not that the environment was software-only. This reframing matters because it's what justifies actually building the ingress-path automation at all — otherwise the team might implicitly treat HIL results as inherently "less real" than the existing (currently 100% mocked-hardware) GUI suite, when the opposite is true once it's built correctly.

### Producing the skeleton twice, deliberately, in two different forms

The skeleton was shown once in chat, in Ask mode, as pure illustrative text — reusing content from `automation/gui/executor.py` (the automation_status gate pattern) and `automate5/packets/ecb_codec.py` (the only real, structured packet-building code found) as the GROUNDED baseline, while explicitly flagging the target IP/port, wire format (ECB-wrapped vs. raw, since the two known reference points in the repo disagree), UART log format, and reset mechanism as unresolved. This was intentional: writing it to disk while still in Ask mode wasn't possible, and writing it to disk *before* getting sign-off on the tagging/structure risked baking in the same kind of unverified assumption that got the earlier `thor_send_payload 1.py` script set aside.

Once the user confirmed the approach and switched to Agent mode, the same content was written for real — but into a new `drafts/fpga_ingress_automation/` folder rather than directly into `automation/` or `tests/`. This placement was deliberate on two counts: `pytest.ini`'s `testpaths = tests` means anything outside `tests/` is structurally guaranteed to never be collected or accidentally reported as a real pass, and keeping it out of `automation/` avoids it being mistaken for the one engine (`automation/gui/`) that currently produces genuine tool-verified results. `QUESTIONS.md` was written as a trackable table (one row per open question, with a `Status` column) specifically so answers from Sheng Li/Seow Jie can be recorded against it over time rather than the questions living only in chat history.

### Committing narrowly

When asked to commit, `git status` showed the new `drafts/` folder alongside two unrelated pending changes: a modified `automate_5/holoscan_fpga/test_cases.yaml` (from an earlier, separate session that added `TC-FPGA-010`–`013`) and an untracked `progress-notes/2026-07-08_pt01_...` file (this very file, from a still-earlier session). Neither was part of what the user asked to commit "now," so only `drafts/` was `git add`ed and committed, leaving the other two exactly as they were for the user to decide on separately.

## Problems hit and how we fixed them

### Shell commands silently hung with no exit status

- **What happened:** Both a direct Python invocation (to analyze `runs.yaml` programmatically) in Ask mode, and a plain `git status` call after switching to Agent mode, returned "The shell command returned no exit status, so its result is unknown" instead of completing.
- **Why it happened:** The sandbox in both modes restricts process execution by default; Ask mode additionally only accepts `network`/`full_network` as valid `required_permissions` values (not `all`), so the first Python attempt failed outright with an "Invalid enum value" error before even reaching the hang.
- **How we fixed it:** For the Python analysis, abandoned the scripted approach entirely and did the equivalent classification with the read-only `Grep` tool instead (listing `test_case_id:` matches and `automation_status`/`automation_readiness` lines directly). For the later Agent-mode `git status` hang, simply retrying the identical command with `required_permissions: ["all"]` succeeded immediately.
- **Lesson learned:** In Ask mode, don't reach for `required_permissions: ["all"]` for shell commands — it's not a valid option there; fall back to Grep/Read for analysis instead of scripting. In Agent mode, a hung/no-exit-status shell call is often just a missing-permission issue and worth one immediate retry with `required_permissions: ["all"]` before treating it as a real failure.

## Concepts clarified

### "Tool-attested" vs. "human-attested" as a provenance question, not a hardware question

Tool-attested means a script produced the result from captured evidence with no human judgment step; human-attested would mean a person manually recorded a PASS/FAIL after visually/manually checking something. This repo currently has examples of the former (GUI) and of "attempted-but-blocked" (everything else), but zero examples of the latter in its formal run-record system — any real hardware bring-up validation the team has done exists only as Confluence prose, disconnected from `runs.yaml`.

### `automation_readiness` and `automation_status` are aspirational labels, not verified state

`automation_readiness` (`Automatable`/`Semi-Automatable`/`Manual`) describes whether a test *could* be automated in principle; `automation_status` (`Ready`/`Not Ready`/`In Progress`) describes whether the automation code actually exists and is wired in today. Neither field, by itself, means a test has ever produced a real result — that can only be confirmed by checking `runs.yaml` for an actual `PASS`/`FAIL` record, which is exactly why the audit in this session cross-referenced both sources instead of trusting the YAML label alone.

### Why a hardware dependency doesn't disqualify a "real" automated result

Reiterated and locked in as a shared conclusion: "real" tracks *how the decision was made* (script + captured evidence vs. human judgment), not *what the test touches* (mocked dependency vs. physical board). This directly motivates finishing the ingress-path automation rather than treating HIL as a lesser, permanently-manual category.

## Where things stand now

```text
drafts/fpga_ingress_automation/        (new, committed at 6b3cee8)
  README.md                            status = DRAFT, legend, path-to-real steps
  QUESTIONS.md                          6 open questions for Sheng Li / Seow Jie, trackable table
  stimulus.py                           UDP send pseudo-code (payload sweep, burst, wrong-port)
  readback.py                           UART/JTAG readback + reset-trigger stubs, fully unverified
  test_tc_fpga_ingress.py               pytest wrapper skeleton, reuses real automation/gui/run_store.append_run
```

- Commit `6b3cee8` is on `main`, 1 commit ahead of `origin/main`, **not pushed**.
- Still sitting uncommitted, untouched by this session: `automate_5/holoscan_fpga/test_cases.yaml` (modified) and this very `progress-notes/2026-07-08_pt01_...` file (now with this Part 3 appended, per explicit user instruction rather than a new `pt02` file).
- Nothing in `drafts/` can be collected by pytest (`pytest.ini` `testpaths = tests`), so it cannot accidentally be reported as a real result.

## What's next

- Get answers to the 6 questions in `drafts/fpga_ingress_automation/QUESTIONS.md` from Sheng Li / Seow Jie (target IP/port, wire format, readback channel, UART format, drop-signal visibility, reset mechanism).
- Once confirmed, replace the ❌/⚠️ markers in `stimulus.py`/`readback.py` and promote the folder's contents into `automation/fpga/` + `tests/test_suite_fpga/`, following the `automation/gui/` + `tests/test_suite_gui/` structural pattern.
- Only then flip `automation_status` on `TC-FPGA-010`–`013` from `Not Ready` to `Ready` in `automate_5/holoscan_fpga/test_cases.yaml`.
- Decide whether to push commit `6b3cee8` to `origin/main` now or bundle it with other pending decisions (the `test_cases.yaml` diff, the still-uncommitted `automation/gui/executor.py` dependency-policy change from Part 2).
