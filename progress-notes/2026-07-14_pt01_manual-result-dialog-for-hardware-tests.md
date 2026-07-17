# Manual Result Dialog for Hardware Tests

> Date: 2026-07-14
> Project / Stage: Automate5 Validation GUI (`scripts/gui.py`)
> Topic: Added an operator-facing manual result flow for hardware-dependent test cases with no automation script, then fixed three follow-on bugs/UX issues in that flow

## What we accomplished

- Added a `ManualResultDialog` class in `scripts/gui.py` that prompts the operator for a manual `PASS`/`FAIL`/`BLOCKED`/`NOT RUN` result (plus notes) for test cases that are hardware-dependent (`test_environment_ci_hil: HIL`) and have no automation script, instead of silently auto-recording them as `BLOCKED`.
- Added `RunFormDialog._is_hardware_dependent()` and `_prompt_manual_result()` to wire the dialog into the batch-execution loop (`_on_save`), branching: `TC-GUI-*` → automated `run_case`; hardware-dependent/no-script → manual prompt; everything else → unchanged auto-`BLOCKED`.
- Fixed a bug where the batch progress window never visibly appeared because a `progress.hide()`/`progress.show()` pair around the manual prompt hid it again before the window manager could paint it.
- Reordered batch execution so hardware-dependent/manual-result test cases run last (`_defer_manual_to_end`, `_needs_manual_result`), and added `_dependency_context()` so the manual dialog shows each dependency's already-recorded result (this run, or latest historical run) and its expected-result text for context.
- Fixed the dialog growing taller than the screen (many dependencies + long text) by wrapping the context section in a scrollable area (matching the existing `DetailDialog` pattern) with a fixed footer (result combo, notes, buttons) and a screen-relative max height (`_size_to_screen`).
- Verified all changes with `python3 -m py_compile`, `ReadLints`, and a headless (`QT_QPA_PLATFORM=offscreen`) smoke test constructing the dialog with 11 dependencies and long text to confirm the capped size and scroll behavior.

## Walkthrough - what we did and why

**1. Manual result prompt instead of auto-BLOCKED.** The user wanted hardware-dependent test cases without automation scripts to be asked about their result manually rather than automatically dictated as `BLOCKED`. Exploring `scripts/gui.py` showed the execution loop in `RunFormDialog._on_save`: only `TC-GUI-*` cases are automatable via `run_case`; everything else was unconditionally recorded `BLOCKED` with a canned note. The fix distinguishes "no script because not yet automated" (still auto-`BLOCKED`, e.g. software/FPGA cases) from "no script because it needs physical hardware" (`test_environment_ci_hil == "HIL"`), and for the latter opens a new `ManualResultDialog` so the operator can enter what actually happened. Declining the dialog ("Skip → Blocked") still falls back to `BLOCKED` with an explanatory note, so behavior is opt-in-to-answer rather than silent.

**2. Progress window not showing.** After that change shipped, the user reported the batch progress window "doesn't show when the run starts." Root-caused it to the manual-prompt branch calling `progress.hide()` right before opening `ManualResultDialog` and `progress.show()` right after — when the first (or only) selected test case is hardware-dependent, this hide/show happens within the same event-loop tick, before the OS/window manager ever paints the progress dialog, so it never becomes visible. Fix: removed the hide/show entirely, since `ManualResultDialog` is its own modal (`.exec()`) and naturally appears on top without needing the progress dialog hidden underneath — this also gives a nicer UX (progress bar stays visible in the background during manual entry).

**3. Deferred manual-result cases to the end + dependency context.** The user asked for two related improvements: (a) run all manual-result-needed test cases at the very end of a batch, and (b) show dependency info (result + expectation) in the prompt, especially for dependencies already executed. Implemented `_defer_manual_to_end`, a stable partition of the already topologically-sorted `tids` list into "auto-resolved" (run first) and "needs manual result" (run last), preserving relative order within each half so dependency ordering still holds. Added `_dependency_context(tid, executed_so_far)`, which looks up each dependency's result — from this batch (`results_by_tid`, tracked incrementally) if already run, else the latest historical run via the existing `latest_run_per_test_case()` — plus its `expected_result` text, and renders it in a new "Dependencies (already run)" section in the dialog, color-coded via the existing `RUN_RESULT_COLORS`.

**4. Dialog height overflow.** With several dependencies and long precondition/expected-result text, the dialog could grow taller than the screen, pushing the result field and Save/Skip buttons out of reach. Wrapped the context section (heading, info, precondition, expected result, dependencies box) in a `QScrollArea`, following the same pattern already used by `DetailDialog` elsewhere in the file (`viewport().setStyleSheet(...)`, `setWidgetResizable(True)`, styled inner `QWidget`). Kept the result combo, notes field, and buttons outside the scroll area so they're always visible. Added `_size_to_screen()` to cap the dialog to at most 640px tall (or 85% of available screen height if smaller) and constrain width similarly, so the window itself can never exceed the screen regardless of content length.

## Problems hit and how we fixed them

### Progress dialog invisible during hardware-dependent runs

- **What happened:** After adding the manual-result prompt, the batch progress window stopped appearing at all when running hardware-dependent test cases.
- **Why it happened:** `progress.hide()` was called immediately upon entering the hardware-dependent branch (to avoid visual overlap with the manual dialog), then `progress.show()` right after — but since hardware tests are often the first or only item in the batch, this hide/show pair executed before the window manager had a chance to actually map/paint the progress window on screen.
- **How we fixed it:** Removed the `hide()`/`show()` calls entirely. `ManualResultDialog` is a proper modal `QDialog` (`.exec()`), so it naturally layers on top of the non-modal progress dialog without needing it hidden first.
- **Lesson learned:** Toggling visibility of a "background" progress dialog around a modal child dialog is unnecessary and risks a show/hide race if the toggle happens on the very first loop iteration — let Qt's window stacking handle it instead.

### Misleading `isVisible()` result while diagnosing in this shell

- **What happened:** While trying to reproduce the progress-dialog bug with a standalone PyQt6 script in the agent's shell, `progress.isVisible()` reported `True` at every step even under conditions that should have hidden it.
- **Why it happened:** This shell environment is missing `libxcb-cursor0`, so Qt silently falls back to the `offscreen` platform plugin (confirmed via `QT_DEBUG_PLUGINS=1`; `app.platformName()` returned `"offscreen"`). `isVisible()` on an offscreen-rendered widget doesn't reflect real on-screen visibility, so this reproduction attempt was a dead end.
- **How we fixed it:** Abandoned the standalone repro and instead reasoned directly from the code path (the `hide()`/`show()` sequencing in `_on_save`), which matched the reported symptom precisely.
- **Lesson learned:** In this sandboxed shell, PyQt6 apps run under the `offscreen` platform plugin by default (missing `libxcb-cursor0`); `isVisible()`/rendering-based smoke tests here only prove "no crash," not real visual behavior. Later smoke tests (e.g. dialog sizing) were scoped to check `size()`/`maximumHeight()` properties instead of relying on visual rendering.

## Concepts clarified

- **Hardware-dependent flag:** a test case is treated as hardware-dependent when its `test_environment_ci_hil` field equals `"HIL"` (vs. `"CI"`). This is set on all `TC-HW-*` (mechanical) cases in the sample data, but also appears on some `TC-GUI`, FPGA, and software cases.
- **Automatable scope:** `RunFormDialog._is_executable_test_case()` only returns `True` for `TC-GUI-*` cases in the `gui` subcomponent — these are the only ones `run_case` (from `automation/gui/executor.py`) can actually execute. Every other subcomponent (software, mechanical, holoscan_fpga, multi_axis_motor_control_fpga) has no automation path today.
- **`QProgressDialog` display timing:** explicit `.show()` + `QApplication.processEvents()` is the standard way to force a progress dialog to render before a synchronous loop runs, but any subsequent `.hide()` call before the event loop has actually flushed the paint/expose events can undo that, especially for fast-completing branches.

## Where things stand now

- `scripts/gui.py` is at 3852 lines (grew from 3596 at the start of this session) and compiles cleanly with no linter errors after every change.
- The full manual-result flow is in place end-to-end: hardware-dependent/no-script cases are deferred to the end of a batch run, prompt via `ManualResultDialog` (now scroll-safe and screen-size-capped) with dependency context, and fall back to `BLOCKED` with an explanatory note if skipped.
- Key new/changed methods on `RunFormDialog`: `_is_hardware_dependent`, `_needs_manual_result`, `_defer_manual_to_end`, `_dependency_context`, `_prompt_manual_result`; new class `ManualResultDialog` (with `_size_to_screen`).
- All fixes so far have been verified via `py_compile`, `ReadLints`, and headless smoke tests (offscreen Qt platform) — none has yet been visually verified on a real display by the user.

## What's next

- No further requests are pending as of this note. If issues resurface, the natural next step would be a real (non-offscreen) manual test of the full batch-run flow with a mix of automated, hardware-dependent, and plain-unautomated test cases to visually confirm ordering, dependency context, and dialog sizing on an actual screen.
