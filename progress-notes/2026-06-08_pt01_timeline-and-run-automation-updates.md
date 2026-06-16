# Timeline And Run Automation Updates

> Date: 2026-06-08
> Project / Stage: Automate validation GUI
> Topic: Added Timeline CSV export, merged Run and Execute behavior, and fixed danger button visibility.

## What we accomplished

- Added a Timeline `Export CSV` button in `scripts/gui.py`.
- Corrected the CSV export so `automate_5_results.csv` contains only populated Timeline result cells, not every test case.
- Merged the standalone Execute behavior into the existing `Run` workflow.
- Removed the separate `Execute` button from the main GUI action bar.
- Updated `RunFormDialog` so saving selected runs executes automation for `TC-GUI-*` cases and records actual results.
- Updated non-executable selected cases to be recorded as `BLOCKED` with an automation-unavailable note.
- Refactored `automation/gui/executor.py` so `run_case(...)` can return an execution result without immediately appending to `runs.yaml`.
- Improved delete/danger button styling so delete buttons use high-contrast red styling with visible text.
- Verified the touched Python files with `py_compile` and linter checks after each substantive change.

## Walkthrough — what we did and why

### Timeline CSV Export

The first request was to add a button in the Timeline window that exports CSV to `automate_5_results.csv`. Initial exploration found that the CLI already had a CSV export path through `scripts/manage_tests.py`, and the first implementation reused that generator from the Timeline dialog.

That produced the same 17-column test-case catalog report as `run.bat report csv`, but the user clarified that the Timeline export should not include all test cases. It should only include the actual results visible in the Timeline.

We then changed the implementation in `scripts/gui.py` so the Timeline export builds CSV rows from Timeline state instead:

- Iterate over each test case ID and work week.
- Use `latest_run_for_cell(self._runs, tid, week)` to find the visible/latest run for that Timeline cell.
- Skip empty cells with no run.
- Write one row per populated Timeline cell.

The resulting CSV columns are focused on Timeline results: `Test Case ID`, `Work Week`, `Date`, `Result`, `Notes`, `Jira Link`, and `Executed By`.

### Run Executes Automation

The next larger change was to make the existing `Run` button function as the old Execute button and remove the separate Execute button entirely.

Before the change, the GUI had two separate paths:

- `Run` opened `RunFormDialog`, where the user could manually save one or more run records with a chosen result.
- `Execute` ran automation only for the currently selected `TC-GUI-*` case and recorded its result separately.

We inspected the existing automation code under `automation/gui/executor.py`. The key behavior was `run_case(...)`, which executed a pytest target and immediately appended a run record using the automation helper's default date/week handling.

To merge the flows cleanly, we changed `run_case(...)` to accept `record: bool = True`. Existing callers can still let it append directly, but `RunFormDialog` can now call it with `record=False`, receive the actual automation result, and then write the run record itself using the user-selected date, work week, Jira link, executed-by value, and notes.

In `RunFormDialog._on_save()`, create mode now:

- Executes `TC-GUI-*` cases through `run_case(..., record=False)`.
- Uses the returned automation result for the saved run record.
- Records non-GUI or otherwise non-executable cases as `BLOCKED`.
- Combines user-entered notes with automation output notes.
- Saves exactly one run record per selected test case.

Edit mode remains manual, so existing run records can still be corrected through the Timeline cell editor.

### Danger Button Visibility

The user reported that the button used to permanently remove a run record from `runs.yaml` had no visible text. The button already had the label `Delete`, so the likely issue was styling: the `danger` button palette was not producing visible foreground text in the actual Qt rendering context.

We first added an explicit foreground color to `QPushButton#danger`, then strengthened the styling further after the user reported it was still not visible. The final change made danger buttons use a darker red background, white text, and a visible border. We also applied the same high-contrast style directly to the delete buttons so the visibility does not depend only on the object-name stylesheet being applied.

## Problems hit and how we fixed them

### Timeline CSV initially exported the wrong dataset

- **What happened:** The first Timeline CSV implementation reused the existing full test-case report generator, so `automate_5_results.csv` contained all test cases rather than only Timeline results.
- **Why it happened:** The README and CLI already had a CSV export named `automate_5_results.csv`, so it was reasonable to reuse it until the user clarified the intended dataset.
- **How we fixed it:** Replaced the generator-based export with Timeline-specific CSV construction based on `latest_run_for_cell(...)`, skipping empty cells.
- **Lesson learned:** A filename match does not imply a data-shape match; UI context matters.

### Default `python` command was unavailable

- **What happened:** Running `python -m py_compile ...` failed with the Windows Store alias message: `Python was not found`.
- **Why it happened:** The system did not have `python` available on `PATH`, but `run.bat` already pointed to an explicit Python 3.13 executable.
- **How we fixed it:** Used `C:/Users/midrus/AppData/Local/Programs/Python/Python313/python.exe` for syntax checks.
- **Lesson learned:** In this workspace, use the configured Python path from `run.bat` for reliable verification.

### Automation runner originally wrote duplicate/default-date records

- **What happened:** The existing `run_case(...)` implementation always appended a run record itself.
- **Why it mattered:** The new Run-dialog workflow needed to execute automation but save records using the dialog's selected date, work week, Jira link, and notes. Letting `run_case(...)` append directly would risk duplicate records and default date/week values.
- **How we fixed it:** Added `record: bool = True` to `run_case(...)` and `_record(...)`, then called `run_case(..., record=False)` from the Run dialog.
- **Lesson learned:** Execution and persistence need to be separable when a higher-level UI owns record metadata.

### Danger button text remained invisible

- **What happened:** The run-record delete button had text, but it was not visibly rendered in the UI.
- **Why it happened:** The app-level `QPushButton#danger` style was not enough in the user's actual rendering context.
- **How we fixed it:** Switched danger buttons to a stronger high-contrast palette and applied a direct `DANGER_BUTTON_STYLE` to the delete buttons.
- **Lesson learned:** For critical destructive actions, direct high-contrast styling is worth using if theme-level styling is unreliable.

### Slash command mismatch for progress notes

- **What happened:** The user invoked `/progress-notes`, but the earlier skill instructions only accepted `/note` or `/progress-note`, so the command was rejected twice.
- **Why it happened:** The manually attached skill content later changed the accepted triggers to `/notes` and `/progress-notes`.
- **How we fixed it:** Once `/progress-notes` was explicitly listed as a trigger in the attached skill, this note was generated.
- **Lesson learned:** Follow the currently attached skill contract when it supersedes earlier assumptions.

## Concepts clarified

- Timeline CSV export should reflect Timeline result state, not the full test-case database.
- The Run workflow now means "execute automation and record actual results" for new records, while editing remains a manual correction path.
- `TC-GUI-*` cases are the executable automation scope; non-GUI selections are recorded as `BLOCKED` rather than silently ignored.
- Separating automation execution from run-record persistence allows the GUI to control metadata such as selected work week and notes.

## Where things stand now

Relevant files changed or involved:

```text
scripts/
  gui.py
automation/
  gui/
    executor.py
    run_store.py
automate_5/
  runs.yaml
progress-notes/
  2026-06-08_pt01_timeline-and-run-automation-updates.md
```

Current GUI behavior:

- Timeline has an `Export CSV` button that writes populated Timeline result cells to `<version>_results.csv`.
- Main window has `Run`, `Timeline`, and `Refresh` actions; the separate `Execute` button has been removed.
- Saving new runs from the Run dialog executes automation for `TC-GUI-*` cases and records results.
- Non-executable selected cases are recorded as `BLOCKED` with an explanatory note.
- Danger/delete buttons use direct high-contrast styling for better visibility.

Verification performed during the session:

- `py_compile` passed for `scripts/gui.py` after GUI edits.
- `py_compile` passed for `scripts/gui.py` and `automation/gui/executor.py` after Run/Execute changes.
- Linter diagnostics reported no errors for the touched files.

## What's next

The next useful step is to smoke-test the GUI manually: open the app, create a multi-select Run, confirm `TC-GUI-*` cases execute and non-GUI cases become `BLOCKED`, then open the Timeline to verify the results and export `automate_5_results.csv`.
