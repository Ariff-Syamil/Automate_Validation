# GUI Test Cases — Automate5 and Validation Repo

> Date: 2026-05-10
> Project / Stage: Automate5 — GUI Validation
> Topic: Designed and wrote 72 structured GUI test cases, added them to both the Automate5 and automate_validation codebases

## What we accomplished

- Explored the Automate5 PySide6/QML codebase to map every testable GUI surface (panels, bridges, presenters, QML components)
- Created `tests/test_suite_gui/gui_test_cases.yaml` in the Automate5 repo — 72 test cases across 15 component areas using the `Automate5_Test_Cases.xlsx`-aligned field schema
- Created `automate_5/gui/test_cases.yaml` in the `automate_validation` repo — the same 72 test cases adapted to that repo's inline YAML style
- Registered the new `gui` subcomponent in both `scripts/manage_tests.py` and `scripts/gui.py` (SUBCOMPONENTS, DISPLAY_NAMES, ALLOWED_PREFIXES, DEFAULT_PREFIX)
- Updated `README.md` in `automate_validation` — added `TC-GUI` row to the ID convention table and `gui/` to the repo structure diagram
- Ran `manage_tests.py validate automate_5`: all 94 test cases (including all 72 new GUI ones) pass with no errors or warnings

## Walkthrough — what we did and why

### Phase 1 — Codebase exploration and planning

Before writing a single test case, the entire Automate5 codebase was explored to understand what was actually testable. This was necessary because the GUI is non-trivial: it uses PySide6 with QML panels loaded via `QQuickWidget`, a bridge/presenter MVP pattern (Python `QObject` bridges expose `Signal`s and `Property`s to QML), and three separate stacked panels (Base, VLA, Analytics).

Key findings that shaped the test design:

- **MainWindow** is a `QStackedWidget` with three pages; navigation is driven by `*_nav_clicked` signals from the LeftRail QML component piped through Python bridges
- **BasePanelBridge** is the richest surface: transport signals (play/stop/reset), motor control signals per (node, motor) index, camera configure/mock, gesture enable/overlay, inspector dock interactions (settings/gestures/logs tabs)
- **VlaPanelBridge** mirrors Base but adds `vla_prompt_submitted(str)` and has no gesture wiring
- **AnalyticPanelBridge** is focused on log/benchmark file I/O: open/refresh/clear for both JSONL logs and CSV benchmarks, display mode picker, and draggable split ratio
- One notable gap: `backend/gesture_controller.py` is imported by `BasePanelPresenter` but the file does not exist — gesture tests were marked `automation_status: Not Ready` with an explicit note in `observations`
- Existing Python test files (`testcase_basePanel.py`, `testcase_vlaPanel.py`, `testcase_analyticPanel.py`) cover bridge defaults and QML compile checks but leave all interaction tests as placeholders

The plan was presented to and confirmed by the user before any files were written.

### Phase 2 — Writing Automate5 YAML (`tests/test_suite_gui/gui_test_cases.yaml`)

Test cases were written using YAML block scalars (`>`) for multi-line string fields, structured under a top-level `test_cases:` key. The 72 entries were grouped by component area in blocks of 10 IDs:

| ID range | Component area |
|---|---|
| TC-GUI-001–003 | Application Window |
| TC-GUI-010–013 | Navigation (LeftRail nav pills) |
| TC-GUI-020–023 | Transport Controls (Play/Stop/Reset) |
| TC-GUI-030–032 | Base Panel / KPI Strip |
| TC-GUI-040–041 | Base Panel / Node Tabs |
| TC-GUI-050–057 | Base Panel / Motor Cards |
| TC-GUI-060–064 | Base Panel / Manual Override Overlay |
| TC-GUI-070–077 | Base Panel / Inspector Dock |
| TC-GUI-100–104 | Base Panel / Camera |
| TC-GUI-110–112 | Base Panel / Gesture Overlay |
| TC-GUI-120–125 | VLA Panel |
| TC-GUI-130–135 | Analytics Panel / Layout & Display |
| TC-GUI-160–164 | Analytics Panel / Logs Pane |
| TC-GUI-170–176 | Analytics Panel / Benchmark Pane |
| TC-GUI-180–182 | QML Compilation |

The YAML was validated using `yaml.safe_load` via a Python one-liner against the venv's Python, confirming all 17 required fields were present in every entry.

### Phase 3 — Adding to `automate_validation`

The `automate_validation` repo has a strictly defined structure: four fixed subcomponents under `automate_5/`, each with a `test_cases.yaml`. The CLI tool (`manage_tests.py`) and desktop GUI (`gui.py`) both hardcode `SUBCOMPONENTS`, `ALLOWED_PREFIXES`, `DISPLAY_NAMES`, and `DEFAULT_PREFIX`.

Since `TC-GUI-*` is a new prefix not previously defined, the cleanest approach was to add a fifth subcomponent `gui/` alongside the existing four. This required:

1. Creating `automate_5/gui/test_cases.yaml` with the 72 test cases reformatted to match the repo's inline string style (no `>` block scalars, shorter one-liner values)
2. Four-line additions to both `manage_tests.py` and `gui.py` (the dicts are parallel between the two files)
3. README updates to keep it in sync as the contributing rules require

## Problems hit and how we fixed them

### Python not on PATH in the workspace shell

- **What happened:** Running `python scripts/manage_tests.py validate automate_5` in the Automate5 workspace shell failed with "Python was not found"
- **Why it happened:** The workspace shell on this Windows machine doesn't have Python on PATH; the system Python is at a fully qualified path
- **How we fixed it:** Read `run.bat` to find the configured Python path (`C:\Users\midrus\AppData\Local\Programs\Python\Python313\python.exe`) and used that directly; also found the Automate5 project has `.venv/Scripts/python` which worked for the YAML validation step
- **Lesson learned:** Always check `run.bat` or the project's launcher script for the correct Python path on this machine before running validation commands

### `automate_validation` has no `.venv`

- **What happened:** Attempted `.venv/Scripts/python` inside `automate_validation`; the directory doesn't exist (`.venv` is generated on first `run.bat` launch)
- **Why it happened:** The repo uses a lazy-init venv approach — `run.bat` creates it on demand but it hadn't been run yet
- **How we fixed it:** Used the system Python313 path directly, which already has `pyyaml` available
- **Lesson learned:** Use the system Python for validation in `automate_validation` until the venv is bootstrapped

## Concepts clarified

### Bridge / Presenter / QML MVP pattern in Automate5

The GUI uses a three-layer pattern:
- **Bridge** (`*_view.py`) — a `QObject` subclass with PySide6 `Signal`s and `Property`s. This is the Python/QML contract: QML reads properties and emits signals; Python connects handlers
- **Presenter** (`*_presenter.py`) — pure Python business logic. It receives signals from the bridge (e.g., `base_start_clicked`) and writes back to bridge properties (e.g., `base_gesture_enabled = True`). The presenter never touches QML directly
- **View** (`*.qml`) — the QML UI, which only references the bridge via context properties (`base_bridge`, `analytic_bridge`, etc.)

This means testability falls into two categories: headless bridge tests (instantiate the bridge and check Python-side signal/property behavior without rendering) and visual/integration tests (show the QQuickWidget and interact via the Qt event loop). The test cases in YAML cover both; the existing Python test files do the headless kind.

### `TC-GUI-NNN` gap numbering is intentional

IDs are grouped in blocks of 10 (001–009, 010–019, …) leaving room for future test cases within each component area without requiring renumbering. This mirrors the pattern used in `TC-FPGA-*` and `TC-SW-*` in the existing validation repo.

## Where things stand now

**`c:\Users\midrus\OneDrive - Lattice Semiconductor Corp\Automate5\`**
```
tests/test_suite_gui/
├── config.yaml
├── conftest.py
├── gui_test_cases.yaml        ← NEW: 72 TC-GUI-* entries, all fields present
├── testcase_analyticPanel.py
├── testcase_basePanel.py
└── testcase_vlaPanel.py
```

**`C:\Users\midrus\OneDrive - Lattice Semiconductor Corp\automate_validation\`**
```
automate_5/
├── gui/
│   └── test_cases.yaml        ← NEW: 72 TC-GUI-* entries, validates clean
├── holoscan_fpga/test_cases.yaml
├── mechanical/test_cases.yaml
├── multi_axis_motor_control_fpga/test_cases.yaml
├── runs.yaml
└── software/test_cases.yaml
scripts/
├── gui.py                     ← UPDATED: gui subcomponent registered
└── manage_tests.py            ← UPDATED: gui subcomponent registered
README.md                      ← UPDATED: TC-GUI row + gui/ in structure
```

Validation output:
```
  software: 4    mechanical: 10    holoscan_fpga: 8
  multi_axis_motor_control_fpga: 0    gui: 72
Validation PASSED.   Total: 94 test cases
```

## What's next

- **Implement the Python test methods** — the YAML now defines what to test; the existing `testcase_basePanel.py` placeholders (test_action1–3) should be replaced with real pytest methods that exercise the signals and bridge properties described in the YAML steps
- **Unblock gesture tests (TC-GUI-110–112)** — `backend/gesture_controller.py` needs to be created or stubbed; once it exists those three cases can move from `Not Ready` to `Ready`
- **Wire YAML to pytest** — consider a loader fixture that reads `gui_test_cases.yaml` and uses `test_case_id` as pytest node IDs, so CI output references `TC-GUI-051` directly
- **Run `run.bat` once** in `automate_validation` to bootstrap the venv, then verify the PyQt6 GUI shows the new GUI subcomponent in the filter dropdown
