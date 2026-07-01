# Run Naming And Timeline Updates

> Date: 2026-06-30
> Project / Stage: Automate validation GUI
> Topic: Added single-run naming, named Timeline filters, and dynamic work-week display

## What we accomplished

- Renamed the run naming flow from "Named Multiple Run" to "Name Run" so a run can be named even when only one test case is selected.
- Updated `scripts/gui.py` so every create-run execution prompts for a run name after dependency expansion.
- Added blank-name fallback behavior: if the user accepts the prompt with an empty name, the run receives the next available `unnamed_N` value, such as `unnamed_1` or `unnamed_2`.
- Ensured every run record created by one execution receives the same `run_name`, whether user-provided or generated.
- Updated Timeline UI text from "run group" wording to "run name" wording while preserving the persisted `run_name` field.
- Changed the valid work-week universe to `WW01` through `WW52` in both `scripts/gui.py` and `automation/gui/run_store.py`.
- Added dynamic Timeline work-week display: result weeks are shown with one WW before and one WW after, bounded to `WW01`-`WW52`.
- Added Timeline column-fill behavior so the grid expands the WW range to fill available table width when there is room, while retaining horizontal scroll for large ranges.
- Updated `automation/gui/run_store.py` so it preserves `run_name` during normalization/save.
- Added focused regression tests in `tests/test_gui_executor.py` for run-name preservation, generated unnamed names, dynamic WW ranges, bounded expansion, no-result fallback, and full-range behavior.
- Verified the touched files with Python compile checks, focused pytest, and IDE lint diagnostics.

## Walkthrough — what we did and why

### Naming every run

The initial request was to change "Named Multiple Run" to "Name Run." The reason was user-facing: naming should not be limited to multi-test batches. Even a single selected test case should be nameable so it can be found and filtered later in the Timeline.

The existing `RunFormDialog` only called the name prompt when `len(tids) > 1`. That meant one-test runs could not receive `run_name`, and therefore could not participate in the existing named Timeline filter. We changed the save flow so the prompt is shown for every create-run execution after dependency expansion confirms there is at least one Ready test to execute.

We kept cancel behavior unchanged: cancelling the prompt cancels the run. But accepting a blank prompt now generates a name like `unnamed_1`. This preserves the new rule that every created execution has a name while still allowing the user to skip typing a custom name.

### Preserving a shared execution name

For a multi-test execution, the Timeline writes one run record per test case. The important invariant is that all records created by the same execution should share the same `run_name`. That lets the Timeline filter show the entire named execution together instead of showing only part of it.

The implementation generates or accepts the run name once before the execution loop and then writes that exact value into every `run_record`. The stored field remains `run_name` for compatibility with existing YAML records and existing filter logic.

### Generalizing Timeline labels

The Timeline filter was already based on `run_name`, but the visible labels still described it as "Named Multiple Run" or "Run Group." That wording became misleading once single-test runs could be named too.

We updated the group box title, delete button, confirmation messages, tooltips, cell tooltip label, and CSV export header to use "Name Run" or "Run Name." Internal method names were left alone where changing them would add churn without changing behavior.

### Dynamic Timeline work-week range

The Timeline originally used a fixed persisted `work_weeks` list. The user asked for the display to show only relevant work weeks: the result WW, one WW before, and one WW after. Later, the requirement was refined so that if the visible table still has empty space, the Timeline should add more WW columns until the visible area is filled. If results span many weeks, the existing horizontal scroll should handle overflow.

We introduced helper logic in `scripts/gui.py` to parse `WWnn` values, derive a bounded display range, and optionally expand that range to a minimum number of visible columns. Result histories expand evenly before and after the padded range. If one side reaches `WW01` or `WW52`, expansion continues on the other side. No-result timelines start at current calendar week ±1 and fill forward.

The Timeline table calculates the minimum number of visible WW columns from the table width and the fixed WW column width. After the user showed a screenshot where the table still had empty blank space, we corrected the calculation to use the full visible table width, use ceiling division, and rebuild after layout settles. We also added resize handling so the Timeline refills columns when the dialog size changes.

### Shared run-store consistency

There are two run persistence paths: `scripts/gui.py` has GUI-local load/save helpers, and `automation/gui/run_store.py` is used by the executor path. The shared run store previously used the old WW17-WW29 default and dropped `run_name` during normalization.

We updated the shared run store to use the same `WW01`-`WW52` universe and to preserve `run_name` when reading/writing records. This keeps executor-recorded runs compatible with Timeline filtering.

### Regression coverage

The focused tests in `tests/test_gui_executor.py` now cover the new behavior without requiring a rendered GUI:

- the run store defaults to `WW01` through `WW52`
- `run_name` survives save/load normalization
- result weeks `WW25` and `WW35` derive `WW24` through `WW36`
- small result spans expand evenly to a requested minimum column count
- no-result timelines start at current WW ±1 and fill forward
- bounds are respected at `WW01` and `WW52`
- a full `WW01`-`WW52` span remains 52 columns
- blank accepted run names produce the next available `unnamed_N`

## Problems hit and how we fixed them

### Plan mode prevented immediate edits

- **What happened:** The first implementation request arrived while Plan mode was active, so file edits were not allowed.
- **Why it happened:** Cursor mode restrictions supersede implementation instructions until the user accepts or switches modes.
- **How we fixed it:** We researched the code, asked the necessary clarification questions, created an implementation plan, and then implemented after the user switched to Agent mode.
- **Lesson learned:** When Plan mode is active, do all needed research and planning first, then wait for explicit execution approval or a mode switch.

### Dynamic range requirement changed after first implementation

- **What happened:** The first plan treated the Timeline range as WW24-WW52. The user then clarified that the visible range should be dynamic around actual result weeks.
- **Why it happened:** The phrase "timeline should start the workweek from WW24 until WW52" was later refined with a specific example: records in WW25 and WW35 should show WW24 through WW36.
- **How we fixed it:** We replaced the fixed range idea with dynamic derivation from recorded `work_week` values, bounded to `WW01`-`WW52`.
- **Lesson learned:** Timeline range behavior needs examples because "start from" can mean either a fixed display range or a bounded universe for dynamic display.

### Python alias unavailable and pytest missing

- **What happened:** `python -m py_compile ...` failed because the `python` command pointed to the Microsoft Store alias. `py -m pytest ...` then found Python 3.13 but reported `No module named pytest`.
- **Why it happened:** The shell does not have a usable `python` command, and the `py` interpreter initially did not have pytest installed.
- **How we fixed it:** We checked `py --version`, confirmed Python 3.13.12, installed the declared `pytest` dependency with `py -m pip install pytest`, then reran validation with `py -m`.
- **Lesson learned:** On this Windows environment, use `py -m ...` for validation commands. The repository declares pytest in `requirements.txt`, but the active interpreter may still need the package installed.

### Timeline still had blank space after column fill

- **What happened:** After the first column-fill implementation, the user showed a screenshot where only a few WW columns were visible and the Timeline table still had unused empty space on the right.
- **Why it happened:** The minimum-column calculation was based on the table viewport too early in the dialog lifecycle, before layout produced the final visible width. It also used floor division, so partial leftover width did not create another WW column.
- **How we fixed it:** We added a zero-delay rebuild after layout settles, recalculated on resize, used the full table width as part of the available-width calculation, and switched to ceiling division.
- **Lesson learned:** GUI sizing logic should account for layout timing. A table width measured before layout can under-fill columns.

## Concepts clarified

### Run name versus run group

The user asked what it meant for every created record in an execution to receive the same `run_name`. The resolved concept is that a single execution can create one record or many records. The shared `run_name` ties those records together so the Timeline filter can show the whole execution consistently.

For example, if five test cases are run under `Regression_1`, all five records get `run_name: Regression_1`. If the name is left blank, all records in that execution might get `run_name: unnamed_1`.

### Valid work-week universe versus displayed work weeks

Another clarified concept was the difference between the full valid set of weeks and the displayed Timeline columns. The application now treats `WW01` through `WW52` as the valid universe for records and date snapping. The Timeline then derives a smaller visible subset from actual results and expands it only enough to fill the visible table area.

### Filled columns versus horizontal scroll

The Timeline should avoid unused blank table space when the result span is small, so it adds surrounding WW columns until the visible area is filled. When the result span is already large, such as `WW01` through `WW52`, it should not compress columns to fit; it keeps fixed-width columns and relies on horizontal scrolling.

## Where things stand now

Relevant changed files:

```text
automation/gui/run_store.py
requirements.txt
scripts/gui.py
tests/test_gui_executor.py
```

Files already dirty from other work remain present in the working tree:

```text
automate_5_results.csv
automation/gui/executor.py
progress-notes/2026-06-30_pt01_skip-not-ready-dependencies.md
scripts/gui.py
tests/test_gui_executor.py
```

Current implementation state:

- The Run dialog prompts for a name for single-test and multi-test executions.
- Blank accepted names auto-generate sequential `unnamed_N` names.
- Every record from one execution receives the same `run_name`.
- Timeline labels now describe the feature as run names, not multiple-run groups.
- The run store preserves `run_name` and uses `WW01`-`WW52` as the valid work-week universe.
- Timeline columns derive from recorded result weeks, include one week of padding, expand to fill visible space, and scroll horizontally for large spans.
- The Timeline rebuilds after layout and on resize so column fill reflects the actual available width.

Validation completed:

- `py -m py_compile scripts/gui.py automation/gui/run_store.py tests/test_gui_executor.py` passed.
- `py -m pytest tests/test_gui_executor.py` passed with 16 tests.
- IDE lint diagnostics reported no errors for `scripts/gui.py`, `automation/gui/run_store.py`, and `tests/test_gui_executor.py`.

## What's next

The immediate next step is to manually exercise the GUI:

- Run a single test case and confirm the `Name Run` prompt appears.
- Accept a blank name and confirm the Timeline shows a generated `unnamed_N` filter.
- Run multiple test cases and confirm all records share one `run_name`.
- Open the Timeline at different window widths and confirm WW columns fill available space without compressing when horizontal scrolling is needed.
