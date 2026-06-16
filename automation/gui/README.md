# GUI Automation Folder

This folder contains the validation-side automation runner for `TC-GUI-*` cases.

- `executor.py` runs one selected test case through Automate5 pytest and records `PASS`, `FAIL`, or `BLOCKED`.
- `run_store.py` appends execution records to `automate_5/runs.yaml`.
- `execution_map.yaml` is only for exceptions; by default `TC-GUI-020` maps to `tests/test_suite_gui/testcase_tc_gui_automation.py::test_tc_gui_020`.

The pytest test implementations live in the Automate5 repo at:

`tests/test_suite_gui/testcase_tc_gui_automation.py`

They stay there so they can import and exercise the Automate5 PySide6/QML application code directly.
