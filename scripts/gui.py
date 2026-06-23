"""
Automate Validation – PyQt6 GUI

Browse, filter, view, and add test cases. The schema mirrors the column
headers in Automate5_Test_Cases.xlsx (sheet 'Automate5_Test_Cases').

Launch:  python scripts/gui.py
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import sys
import uuid
from pathlib import Path

import yaml
from PyQt6.QtCore import Qt, QSortFilterProxyModel, QDate
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableView, QHeaderView, QPushButton, QComboBox, QLabel,
    QDialog, QFormLayout, QLineEdit, QTextEdit, QDateEdit,
    QMessageBox, QGroupBox, QFrame, QInputDialog,
    QScrollArea, QAbstractItemView, QListWidget, QListWidgetItem,
)

try:
    from automation.gui import run_case
except ImportError:  # pragma: no cover - supports unusual direct import contexts
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from automation.gui import run_case

# ── Data layer ──────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent

SUBCOMPONENTS: list[str] = [
    "software",
    "mechanical",
    "holoscan_fpga",
    "multi_axis_motor_control_fpga",
    "gui",
]

DISPLAY_NAMES: dict[str, str] = {
    "software": "Software",
    "mechanical": "Mechanical",
    "holoscan_fpga": "Holoscan FPGA",
    "multi_axis_motor_control_fpga": "Multi Axis Motor Control FPGA",
    "gui": "GUI",
}

# Allowed Test Case ID prefixes per subcomponent folder.
ALLOWED_PREFIXES: dict[str, tuple[str, ...]] = {
    "software": ("TC-SW", "TC-SYS"),
    "mechanical": ("TC-HW",),
    "holoscan_fpga": ("TC-FPGA", "TC-VLA"),
    "multi_axis_motor_control_fpga": ("TC-MAMC",),
    "gui": ("TC-GUI",),
}

# Default prefix used when generating new IDs from the Add dialog.
DEFAULT_PREFIX: dict[str, str] = {
    "software": "TC-SW",
    "mechanical": "TC-HW",
    "holoscan_fpga": "TC-FPGA",
    "multi_axis_motor_control_fpga": "TC-MAMC",
    "gui": "TC-GUI",
}

# Suggested values for editable dropdowns in the Add dialog.
PRIORITY_OPTIONS = ("", "P0", "P1", "P2", "P3")
SEVERITY_OPTIONS = ("", "Critical", "Major", "Minor")
AUTOMATION_READINESS_OPTIONS = ("", "Automatable", "Semi-Automatable", "Manual")
AUTOMATION_STATUS_OPTIONS = ("", "Ready", "Not Ready", "In Progress", "Blocked")
ENVIRONMENT_OPTIONS = ("", "CI", "HIL")


def discover_versions() -> list[str]:
    """Find all `automate_*` directories in the repo root."""
    return sorted(
        d.name for d in REPO_ROOT.iterdir()
        if d.is_dir() and d.name.startswith("automate_")
    )


def discover_test_files(automate_dir: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for sub in SUBCOMPONENTS:
        p = automate_dir / sub / "test_cases.yaml"
        if p.exists():
            found[sub] = p
    return found


def load_test_cases(yaml_path: Path) -> list[dict]:
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("test_cases", []) if data else []


def save_test_cases(yaml_path: Path, test_cases: list[dict]) -> None:
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {"test_cases": test_cases},
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=100,
        )


# Default work-week range used when runs.yaml does not yet exist.
DEFAULT_WORK_WEEKS: tuple[str, ...] = tuple(f"WW{n:02d}" for n in range(17, 30))

# Allowed run-result values.
RUN_RESULTS: tuple[str, ...] = (
    "PASS", "FAIL", "NOT RUN", "IN PROGRESS", "BLOCKED",
)

# (background, foreground) tints for each result, used to colour timeline cells.
RUN_RESULT_COLORS: dict[str, tuple[str, str]] = {
    "PASS":        ("#1d3a1d", "#a6e3a1"),
    "FAIL":        ("#3b1620", "#f38ba8"),
    "NOT RUN":     ("#2a2a3a", "#a6adc8"),
    "IN PROGRESS": ("#3a2f1a", "#fab387"),
    "BLOCKED":     ("#3a1c2a", "#cba6f7"),
}

# Header labels for the computed summary in the Timeline header.
METRIC_LABELS: tuple[str, ...] = ("% PASS", "% FAIL", "% NOT RUN")

DANGER_BUTTON_STYLE = (
    "background-color: #c0392b;"
    "color: #ffffff;"
    "border: 1px solid #ffb4a8;"
    "border-radius: 6px;"
    "padding: 7px 18px;"
    "font-weight: bold;"
)


def _coerce_duration_seconds(value) -> float | None:
    """Return a non-negative duration in seconds, or None if absent/invalid."""
    if value in (None, ""):
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if seconds < 0:
        return None
    return round(seconds, 3)


def format_duration(value) -> str:
    """Format stored duration seconds for Timeline display/export."""
    seconds = _coerce_duration_seconds(value)
    if seconds is None:
        return ""
    total = int(round(seconds))
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {secs:02d}s"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins:02d}m"


def format_total_duration(runs: list[dict]) -> str:
    """Format the sum of stored run durations."""
    total = 0.0
    for run in runs:
        seconds = _coerce_duration_seconds(run.get("duration_seconds"))
        if seconds is not None:
            total += seconds
    return format_duration(total)


def runs_path(version: str) -> Path:
    return REPO_ROOT / version / "runs.yaml"


def _all_test_case_ids(version: str) -> list[str]:
    """Every test_case_id in the YAML database for `version`, in folder order."""
    ids: list[str] = []
    automate_dir = REPO_ROOT / version
    for sub in SUBCOMPONENTS:
        path = automate_dir / sub / "test_cases.yaml"
        if not path.exists():
            continue
        for tc in load_test_cases(path):
            tid = tc.get("test_case_id")
            if tid:
                ids.append(tid)
    return ids


def _normalise_run(raw: dict) -> dict | None:
    """Return a clean copy of a run record, or None if essential fields missing."""
    if not isinstance(raw, dict):
        return None
    tid = (raw.get("test_case_id") or "").strip()
    week = (raw.get("work_week") or "").strip()
    if not tid or not week:
        return None
    date = raw.get("date")
    if isinstance(date, (_dt.date, _dt.datetime)):
        date = date.isoformat()[:10]
    elif date is not None:
        date = str(date).strip()
    result = (raw.get("result") or "NOT RUN").strip().upper()
    if result not in RUN_RESULTS:
        result = "NOT RUN"
    clean = {
        "id":           str(raw.get("id") or uuid.uuid4().hex[:12]),
        "test_case_id": tid,
        "date":         date or "",
        "work_week":    week,
        "result":       result,
        "notes":        (raw.get("notes") or "").strip(),
        "jira_link":    (raw.get("jira_link") or "").strip(),
        "executed_by":  (raw.get("executed_by") or "").strip(),
        "created_at":   str(raw.get("created_at") or _dt.datetime.now().isoformat(timespec="seconds")),
    }
    run_name = (raw.get("run_name") or "").strip()
    if run_name:
        clean["run_name"] = run_name
    duration = _coerce_duration_seconds(raw.get("duration_seconds"))
    if duration is not None:
        clean["duration_seconds"] = duration
    return clean


def load_runs(version: str) -> dict:
    """Load `automate_5/runs.yaml` (creating a default scaffold if missing).

    Returned dict shape::

        {
            "year":       2026,                # int
            "work_weeks": ["WW17", ...],
            "runs":       [run_record, ...],
        }
    """
    path = runs_path(version)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    work_weeks: list[str] = list(data.get("work_weeks") or DEFAULT_WORK_WEEKS)

    year = data.get("year")
    try:
        year = int(year) if year is not None else _dt.date.today().year
    except (TypeError, ValueError):
        year = _dt.date.today().year

    runs: list[dict] = []
    for raw in (data.get("runs") or []):
        clean = _normalise_run(raw)
        if clean is not None:
            runs.append(clean)

    return {"year": year, "work_weeks": work_weeks, "runs": runs}


def save_runs(version: str, state: dict) -> None:
    """Write the runs state back to disk (preserves YAML banner)."""
    path = runs_path(version)
    path.parent.mkdir(parents=True, exist_ok=True)

    runs_clean: list[dict] = []
    for r in (state.get("runs") or []):
        clean = _normalise_run(r)
        if clean is not None:
            runs_clean.append(clean)

    payload = {
        "year": int(state.get("year") or _dt.date.today().year),
        "work_weeks": list(state.get("work_weeks") or DEFAULT_WORK_WEEKS),
        "runs": runs_clean,
    }

    banner = (
        "# =============================================================================\n"
        "# Automate 5 - Test-Case Run Records\n"
        "# =============================================================================\n"
        "# Append-only log of test-case executions. Edit/delete is done via the GUI's\n"
        "# Timeline view. The Timeline is purely a visualisation of these records.\n"
        "# =============================================================================\n\n"
    )
    body = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100)
    path.write_text(banner + body, encoding="utf-8")


def runs_for_cell(runs: list[dict], tid: str, week: str) -> list[dict]:
    """All runs for (test_case_id, work_week), newest first."""
    matches = [r for r in runs if r.get("test_case_id") == tid and r.get("work_week") == week]
    matches.sort(key=lambda r: (r.get("date") or "", r.get("created_at") or ""), reverse=True)
    return matches


def latest_run_for_cell(runs: list[dict], tid: str, week: str) -> dict | None:
    cell = runs_for_cell(runs, tid, week)
    return cell[0] if cell else None


def latest_run_per_test_case(runs: list[dict]) -> dict[str, dict]:
    """Map test_case_id -> the most recent run record (across all weeks)."""
    out: dict[str, dict] = {}
    for r in runs:
        tid = r.get("test_case_id")
        if not tid:
            continue
        key = (r.get("date") or "", r.get("created_at") or "")
        existing = out.get(tid)
        if not existing:
            out[tid] = r
            continue
        existing_key = (existing.get("date") or "", existing.get("created_at") or "")
        if key > existing_key:
            out[tid] = r
    return out


def compute_run_metrics(runs: list[dict], all_test_case_ids: list[str]) -> dict[str, str]:
    """Return {'% PASS': '12%', '% FAIL': '5%', '% NOT RUN': '83%'} for the
    header strip on the Timeline view, computed from latest run per test case.

    A test case with no runs at all counts as NOT RUN.
    """
    total = len(all_test_case_ids)
    if total == 0:
        return {label: "0%" for label in METRIC_LABELS}

    latest = latest_run_per_test_case(runs)
    pass_n  = sum(1 for tid in all_test_case_ids
                  if latest.get(tid, {}).get("result") == "PASS")
    fail_n  = sum(1 for tid in all_test_case_ids
                  if latest.get(tid, {}).get("result") == "FAIL")
    not_run = sum(1 for tid in all_test_case_ids
                  if tid not in latest or latest[tid].get("result") == "NOT RUN")

    return {
        "% PASS":    f"{pass_n   / total * 100:.0f}%  ({pass_n}/{total})",
        "% FAIL":    f"{fail_n   / total * 100:.0f}%  ({fail_n}/{total})",
        "% NOT RUN": f"{not_run  / total * 100:.0f}%  ({not_run}/{total})",
    }


def current_work_week(date: _dt.date, valid_weeks: list[str]) -> str | None:
    """Return the WWnn label for `date` if it falls in `valid_weeks`, else None."""
    iso = date.isocalendar().week
    candidate = f"WW{iso:02d}"
    return candidate if candidate in valid_weeks else None


def id_prefix(test_case_id: str) -> str:
    parts = test_case_id.split("-")
    if len(parts) <= 1:
        return test_case_id
    return "-".join(parts[:-1])


def next_test_id(existing_cases: list[dict], prefix: str, pad: int = 3) -> str:
    """Compute the next sequential test_case_id for a given prefix."""
    max_num = 0
    used_pad = pad
    for tc in existing_cases:
        tid = (tc.get("test_case_id") or "").strip()
        if id_prefix(tid) != prefix:
            continue
        num_part = tid.split("-")[-1]
        try:
            max_num = max(max_num, int(num_part))
            used_pad = max(used_pad, len(num_part))
        except ValueError:
            continue
    return f"{prefix}-{max_num + 1:0{used_pad}d}"


def folder_for_prefix(prefix: str) -> str | None:
    """Return the subcomponent folder that owns a given ID prefix."""
    for sub, prefixes in ALLOWED_PREFIXES.items():
        if prefix in prefixes:
            return sub
    return None


# ── Stylesheet ───────────────────────────────────────────────────────────────

STYLESHEET = """
QMainWindow, QDialog {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QLabel {
    color: #cdd6f4;
    font-size: 13px;
}
QLabel#heading {
    font-size: 20px;
    font-weight: bold;
    color: #89b4fa;
    padding: 4px 0;
}
QLabel#subheading {
    font-size: 13px;
    color: #a6adc8;
}
QComboBox, QDateEdit, QSpinBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 5px 10px;
    min-width: 140px;
    font-size: 13px;
}
QComboBox:focus, QDateEdit:focus, QSpinBox:focus {
    border: 1px solid #89b4fa;
}
QComboBox::drop-down, QDateEdit::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #313244;
    color: #cdd6f4;
    selection-background-color: #585b70;
    border: 1px solid #45475a;
    outline: 0;
}
/* The internal QLineEdit of an editable QComboBox / QDateEdit /
   QSpinBox renders white-on-white by default; force the dark theme. */
QComboBox QLineEdit, QDateEdit QLineEdit, QSpinBox QLineEdit,
QAbstractSpinBox QLineEdit {
    background-color: #313244;
    color: #cdd6f4;
    border: none;
    padding: 0;
}
/* Make the calendar popup match the dark theme too. */
QCalendarWidget QWidget { background-color: #1e1e2e; color: #cdd6f4; }
QCalendarWidget QAbstractItemView:enabled {
    background-color: #1e1e2e;
    color: #cdd6f4;
    selection-background-color: #585b70;
}
QCalendarWidget QToolButton {
    background-color: #313244;
    color: #cdd6f4;
    border: none;
    padding: 4px 8px;
}
QCalendarWidget QSpinBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
}
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 6px;
    padding: 7px 18px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #74c7ec;
}
QPushButton:pressed {
    background-color: #89dceb;
}
QPushButton#danger {
    background-color: #c0392b;
    color: #ffffff;
    border: 1px solid #ffb4a8;
}
QPushButton#danger:hover {
    background-color: #e74c3c;
    color: #ffffff;
    border: 1px solid #ffd0c8;
}
QPushButton#success {
    background-color: #a6e3a1;
}
QPushButton#success:hover {
    background-color: #94e2d5;
}
QPushButton#secondary {
    background-color: #585b70;
    color: #cdd6f4;
}
QPushButton#secondary:hover {
    background-color: #6c7086;
}
QTableView {
    background-color: #181825;
    alternate-background-color: #1e1e2e;
    color: #cdd6f4;
    gridline-color: #313244;
    border: 1px solid #313244;
    border-radius: 8px;
    font-size: 13px;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
}
QTableView::item {
    padding: 4px 8px;
}
QHeaderView::section {
    background-color: #313244;
    color: #89b4fa;
    border: none;
    border-bottom: 2px solid #89b4fa;
    padding: 6px 8px;
    font-weight: bold;
    font-size: 12px;
}
QLineEdit, QTextEdit {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 13px;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #89b4fa;
}
QListWidget {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 4px;
    font-size: 13px;
}
QListWidget::item {
    padding: 5px 8px;
    border-radius: 4px;
}
QListWidget::item:hover { background-color: #313244; }
QListWidget::item:selected {
    background-color: #45475a;
    color: #cdd6f4;
}
QGroupBox {
    border: 1px solid #45475a;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 18px;
    font-weight: bold;
    font-size: 13px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #89b4fa;
}
QGroupBox QLabel {
    color: #cdd6f4;
    font-weight: normal;
}
QLabel[role="fieldLabel"] {
    color: #a6adc8;
    font-weight: normal;
}
QLabel[role="fieldValue"] {
    color: #cdd6f4;
    font-weight: normal;
}
QLabel[role="fieldValueEmpty"] {
    color: #6c7086;
    font-style: italic;
}
QScrollBar:vertical {
    background: #181825;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #585b70;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QMessageBox {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QScrollArea {
    background-color: #1e1e2e;
    border: none;
}
QWidget#dialogContent {
    background-color: #1e1e2e;
}
QFrame {
    background-color: transparent;
}
"""

# ── Colours ──────────────────────────────────────────────────────────────────

COLOR_P0      = QColor("#f38ba8")
COLOR_P1      = QColor("#fab387")
COLOR_P2      = QColor("#f9e2af")
COLOR_P3      = QColor("#a6e3a1")
COLOR_DEFAULT = QColor("#a6adc8")
COLOR_READY   = QColor("#a6e3a1")
COLOR_NOT_RDY = QColor("#f38ba8")
COLOR_WIP     = QColor("#fab387")

PRIORITY_COLOR = {
    "P0": COLOR_P0,
    "P1": COLOR_P1,
    "P2": COLOR_P2,
    "P3": COLOR_P3,
}

AUTO_STATUS_COLOR = {
    "Ready": COLOR_READY,
    "Not Ready": COLOR_NOT_RDY,
    "In Progress": COLOR_WIP,
    "Blocked": COLOR_NOT_RDY,
}

# Table columns mirror the catalog fields shown in the GUI.
# Tuple shape: (display header, dict key, default width px).
TABLE_COLUMNS: tuple[tuple[str, str, int], ...] = (
    ("Test Case ID",              "test_case_id",            120),
    ("Owner",                     "owner",                   140),
    ("Component",                 "component",               160),
    ("Dependency",                "dependency",              180),
    ("PreCondition",              "precondition",            140),
    ("Test Name",                 "test_name",               220),
    ("Description",               "description",             280),
    ("Steps",                     "steps",                   320),
    ("Expected Result",           "expected_result",         260),
    ("Fail Conditions",           "fail_conditions",         220),
    ("Priority",                  "priority",                 80),
    ("Severity",                  "severity",                 90),
    ("Automation Readiness",      "automation_readiness",    150),
    ("Automation Status",         "automation_status",       140),
    ("Test Environment (CI/HIL)", "test_environment_ci_hil", 130),
    ("Observations",              "observations",            220),
    ("Jira Link",                 "jira_link",               140),
    ("Next Action (if Fail)",     "next_action_if_fail",     240),
)


# ═══════════════════════════════════════════════════════════════════════════
#  Detail Dialog – shows full test case info (read-only)
# ═══════════════════════════════════════════════════════════════════════════

class DetailDialog(QDialog):
    """Read-only detail view. Emits `edit_requested` (via dialog code) when
    the user clicks Edit; the parent re-opens the test case in edit mode."""

    EDIT_REQUESTED = QDialog.DialogCode.Accepted + 1  # custom code

    def __init__(self, tc: dict, parent=None):
        super().__init__(parent)
        self._tc = tc
        tid = tc.get("test_case_id", "")
        self.setWindowTitle(f"Test Case – {tid}")
        self.setMinimumSize(720, 640)

        outer = QVBoxLayout(self)
        outer.setSpacing(8)
        outer.setContentsMargins(14, 12, 14, 12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.viewport().setStyleSheet("background-color: #1e1e2e;")
        inner = QWidget()
        inner.setObjectName("dialogContent")
        inner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(inner)
        layout.setSpacing(12)

        hdr = QLabel(f"{tid}  —  {tc.get('test_name', '')}")
        hdr.setObjectName("heading")
        layout.addWidget(hdr)

        sub_text = tc.get("component") or DISPLAY_NAMES.get(
            folder_for_prefix(id_prefix(tid)) or "", ""
        )
        if sub_text:
            sub = QLabel(sub_text)
            sub.setObjectName("subheading")
            layout.addWidget(sub)

        desc = tc.get("description")
        if desc:
            desc_lbl = self._make_value_label(desc)
            desc_lbl.setObjectName("description")
            layout.addWidget(desc_lbl)

        meta = self._build_form_group(
            "Metadata",
            [
                ("Owner",                tc.get("owner")),
                ("Component",            tc.get("component")),
                ("PreCondition",         tc.get("precondition")),
                ("Priority",             tc.get("priority")),
                ("Severity",             tc.get("severity")),
                ("Automation Readiness", tc.get("automation_readiness")),
                ("Automation Status",    tc.get("automation_status")),
                ("Test Environment",     tc.get("test_environment_ci_hil")),
                ("Jira Link",            tc.get("jira_link")),
            ],
        )
        layout.addWidget(meta)

        deps = tc.get("dependency") or []
        deps_grp = QGroupBox(f"Dependencies ({len(deps)})")
        dl = QVBoxLayout(deps_grp)
        deps_lbl = self._make_value_label(", ".join(deps) if deps else None)
        dl.addWidget(deps_lbl)
        layout.addWidget(deps_grp)

        steps = tc.get("steps") or []
        steps_grp = QGroupBox(f"Steps ({len(steps)})")
        sl = QVBoxLayout(steps_grp)
        sl.setSpacing(4)
        if steps:
            for i, step in enumerate(steps, 1):
                row = self._make_value_label(f"{i}.  {step}")
                sl.addWidget(row)
        else:
            sl.addWidget(self._make_value_label(None))
        layout.addWidget(steps_grp)

        crit = self._build_form_group(
            "Pass / Fail Criteria",
            [
                ("Expected Result", tc.get("expected_result")),
                ("Fail Conditions", tc.get("fail_conditions")),
            ],
        )
        layout.addWidget(crit)

        notes = self._build_form_group(
            "Notes",
            [
                ("Observations",         tc.get("observations")),
                ("Next Action (if Fail)", tc.get("next_action_if_fail")),
            ],
        )
        layout.addWidget(notes)

        layout.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        # Bottom button row: Edit + Close
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_edit = QPushButton("✎  Edit")
        btn_edit.setObjectName("success")
        btn_edit.clicked.connect(self._on_edit)
        btn_row.addWidget(btn_edit)
        btn_close = QPushButton("Close")
        btn_close.setObjectName("secondary")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        outer.addLayout(btn_row)

    def _on_edit(self) -> None:
        # Use a custom done() code so the parent knows to open the editor.
        self.done(self.EDIT_REQUESTED)

    # --- helpers ------------------------------------------------------------

    def _build_form_group(self, title: str, rows: list[tuple[str, object]]) -> QGroupBox:
        grp = QGroupBox(title)
        form = QFormLayout(grp)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        for label_text, value in rows:
            form.addRow(self._make_field_label(label_text + ":"),
                        self._make_value_label(value))
        return grp

    @staticmethod
    def _make_field_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("role", "fieldLabel")
        lbl.setMinimumWidth(150)
        return lbl

    @staticmethod
    def _make_value_label(value) -> QLabel:
        is_empty = value in (None, "")
        text = "(empty)" if is_empty else str(value)
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setProperty("role", "fieldValueEmpty" if is_empty else "fieldValue")
        lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        return lbl


# ═══════════════════════════════════════════════════════════════════════════
#  Test Case Form Dialog (Add + Edit)
# ═══════════════════════════════════════════════════════════════════════════

class TestCaseFormDialog(QDialog):
    """Dialog for both creating new test cases and editing existing ones.

    Pass `existing_tc=None` (default) to add a new test case. Pass an existing
    YAML dict to open the form in edit mode: subcomponent + ID become read-only,
    a Delete Test Case button appears, and on save the test case is updated
    in-place in its file.

    `existing_subcomponent` is required in edit mode so we know which YAML
    file owns the record.

    Return codes (use ``exec()``):
      * ``QDialog.DialogCode.Accepted`` – test case was added or updated.
      * ``DELETED``                     – test case was removed (edit mode only).
      * ``QDialog.DialogCode.Rejected`` – cancel.
    """

    DELETED = QDialog.DialogCode.Accepted + 2  # custom code

    def __init__(
        self,
        version: str,
        existing_tc: dict | None = None,
        existing_subcomponent: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.version = version
        self._existing = existing_tc
        self._existing_sub = existing_subcomponent
        self._is_edit = existing_tc is not None

        if self._is_edit:
            self.setWindowTitle(f"Edit Test Case – {existing_tc.get('test_case_id', '')}")
        else:
            self.setWindowTitle("Add New Test Case")
        self.setMinimumSize(640, 420)
        self.resize(720, 560)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.viewport().setStyleSheet("background-color: #1e1e2e;")
        inner = QWidget()
        inner.setObjectName("dialogContent")
        inner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        body = QVBoxLayout(inner)
        body.setSpacing(10)

        # -- Identification (subcomponent + ID + name) --
        routing = QGroupBox("Identification")
        rl = QFormLayout(routing)
        rl.setHorizontalSpacing(14)
        rl.setVerticalSpacing(8)

        self.combo_sub = QComboBox()
        for s in SUBCOMPONENTS:
            self.combo_sub.addItem(DISPLAY_NAMES[s], s)
        self.combo_sub.currentIndexChanged.connect(self._on_subcomponent_changed)
        rl.addRow(self._make_field_label("Subcomponent:"), self.combo_sub)

        self.combo_prefix = QComboBox()
        self.combo_prefix.currentIndexChanged.connect(self._update_id_preview)
        rl.addRow(self._make_field_label("ID Prefix:"), self.combo_prefix)

        self.lbl_id = QLabel()
        self.lbl_id.setStyleSheet("color: #89b4fa; font-weight: bold; font-size: 14px;")
        id_label = "Test Case ID:" if self._is_edit else "Test Case ID (auto):"
        rl.addRow(self._make_field_label(id_label), self.lbl_id)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Short descriptive name")
        rl.addRow(self._make_field_label("Test Name:"), self.txt_name)

        self.txt_description = QTextEdit()
        self.txt_description.setPlaceholderText("Plain-language explanation for a non-expert user")
        self.txt_description.setMinimumHeight(70)
        rl.addRow(self._make_field_label("Description:"), self.txt_description)

        body.addWidget(routing)

        # -- Metadata --
        meta = QGroupBox("Metadata")
        ml = QFormLayout(meta)
        ml.setHorizontalSpacing(14)
        ml.setVerticalSpacing(8)

        self.txt_owner = QLineEdit()
        self.txt_owner.setPlaceholderText("Person or pair, e.g. Jane Doe / Bob")
        ml.addRow(self._make_field_label("Owner:"), self.txt_owner)

        self.txt_component = QLineEdit()
        self.txt_component.setPlaceholderText("Functional area, e.g. UDP Communication")
        ml.addRow(self._make_field_label("Component:"), self.txt_component)

        self.txt_precondition = QLineEdit()
        self.txt_precondition.setPlaceholderText("Required setup or hardware state")
        ml.addRow(self._make_field_label("PreCondition:"), self.txt_precondition)

        self.combo_priority = self._editable_combo(PRIORITY_OPTIONS)
        ml.addRow(self._make_field_label("Priority:"), self.combo_priority)

        self.combo_severity = self._editable_combo(SEVERITY_OPTIONS)
        ml.addRow(self._make_field_label("Severity:"), self.combo_severity)

        self.combo_readiness = self._editable_combo(AUTOMATION_READINESS_OPTIONS)
        ml.addRow(self._make_field_label("Automation Readiness:"), self.combo_readiness)

        self.combo_status = self._editable_combo(AUTOMATION_STATUS_OPTIONS)
        ml.addRow(self._make_field_label("Automation Status:"), self.combo_status)

        self.combo_env = self._editable_combo(ENVIRONMENT_OPTIONS)
        ml.addRow(self._make_field_label("Test Environment (CI/HIL):"), self.combo_env)

        self.txt_jira = QLineEdit()
        self.txt_jira.setPlaceholderText("https://…")
        ml.addRow(self._make_field_label("Jira Link:"), self.txt_jira)

        body.addWidget(meta)

        # -- Dependencies --
        deps_grp = QGroupBox("Dependency")
        dl = QVBoxLayout(deps_grp)
        self.txt_deps = QLineEdit()
        self.txt_deps.setPlaceholderText(
            "Comma- or newline-separated test_case_ids, e.g. TC-FPGA-001, TC-FPGA-002"
        )
        dl.addWidget(self.txt_deps)
        body.addWidget(deps_grp)

        # -- Steps --
        steps_grp = QGroupBox("Steps")
        sl = QVBoxLayout(steps_grp)
        hint = QLabel("One step per line.")
        hint.setProperty("role", "fieldLabel")
        sl.addWidget(hint)
        self.txt_steps = QTextEdit()
        self.txt_steps.setPlaceholderText("Connect camera\nLoad bitstream\nStart pipeline")
        self.txt_steps.setMinimumHeight(80)
        sl.addWidget(self.txt_steps)
        body.addWidget(steps_grp)

        # -- Criteria --
        crit = QGroupBox("Pass / Fail Criteria")
        cl = QFormLayout(crit)
        cl.setHorizontalSpacing(14)
        cl.setVerticalSpacing(8)
        self.txt_expected = QLineEdit()
        self.txt_expected.setPlaceholderText("What constitutes a passing test")
        cl.addRow(self._make_field_label("Expected Result:"), self.txt_expected)
        self.txt_fail = QLineEdit()
        self.txt_fail.setPlaceholderText("What constitutes a failing test")
        cl.addRow(self._make_field_label("Fail Conditions:"), self.txt_fail)
        body.addWidget(crit)

        # -- Notes --
        notes = QGroupBox("Notes")
        nl = QFormLayout(notes)
        nl.setHorizontalSpacing(14)
        nl.setVerticalSpacing(8)
        self.txt_observations = QLineEdit()
        self.txt_observations.setPlaceholderText("Free-form context")
        nl.addRow(self._make_field_label("Observations:"), self.txt_observations)
        self.txt_next = QLineEdit()
        self.txt_next.setPlaceholderText("Triage / debug hint if the test fails")
        nl.addRow(self._make_field_label("Next Action (if Fail):"), self.txt_next)
        body.addWidget(notes)

        body.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        # ── Bottom button row: Delete (edit mode only) | Cancel | Save ──────
        btn_row = QHBoxLayout()
        if self._is_edit:
            btn_delete = QPushButton("Delete Test Case")
            btn_delete.setObjectName("danger")
            btn_delete.setStyleSheet(DANGER_BUTTON_STYLE)
            btn_delete.setToolTip(
                "Permanently remove this test case from its YAML file. "
                "Run records in runs.yaml are NOT touched."
            )
            btn_delete.clicked.connect(self._on_delete)
            btn_row.addWidget(btn_delete)
        btn_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("Save Changes" if self._is_edit else "Save")
        btn_save.setObjectName("success")
        btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(btn_save)

        outer.addLayout(btn_row)

        # Initialise combos and routing.
        if self._is_edit:
            self._init_edit_mode()
        else:
            self._on_subcomponent_changed()

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _editable_combo(options: tuple[str, ...]) -> QComboBox:
        """Fixed dropdown — values are restricted to the given options.
        The first option is conventionally the empty string for "(none)"."""
        box = QComboBox()
        box.setEditable(False)
        for o in options:
            box.addItem(o if o else "(none)", o)
        box.setCurrentIndex(0)
        return box

    @staticmethod
    def _make_field_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("role", "fieldLabel")
        return lbl

    @staticmethod
    def _none_if_blank(value) -> str | None:
        if value is None:
            return None
        text = value.strip() if isinstance(value, str) else value
        return text or None

    @staticmethod
    def _select_combo_value(combo: QComboBox, value) -> None:
        """Select the item in `combo` whose underlying data matches `value`.
        Falls back to index 0 if no match is found."""
        target = "" if value is None else str(value)
        for i in range(combo.count()):
            if combo.itemData(i) == target:
                combo.setCurrentIndex(i)
                return
        combo.setCurrentIndex(0)

    def _on_subcomponent_changed(self) -> None:
        sub = self.combo_sub.currentData()
        prefixes = ALLOWED_PREFIXES.get(sub, ())
        self.combo_prefix.blockSignals(True)
        self.combo_prefix.clear()
        for p in prefixes:
            self.combo_prefix.addItem(p, p)
        default = DEFAULT_PREFIX.get(sub)
        if default:
            idx = self.combo_prefix.findData(default)
            if idx >= 0:
                self.combo_prefix.setCurrentIndex(idx)
        self.combo_prefix.blockSignals(False)
        self._update_id_preview()

    def _update_id_preview(self) -> None:
        if self._is_edit:
            return  # ID is fixed in edit mode
        sub = self.combo_sub.currentData()
        prefix = self.combo_prefix.currentData()
        if not sub or not prefix:
            self.lbl_id.setText("")
            return
        cases = self._load_sub_cases(sub)
        self.lbl_id.setText(next_test_id(cases, prefix))

    def _load_sub_cases(self, sub: str) -> list[dict]:
        p = REPO_ROOT / self.version / sub / "test_cases.yaml"
        return load_test_cases(p) if p.exists() else []

    def _init_edit_mode(self) -> None:
        """Populate fields from `_existing` and lock identifying fields."""
        tc = self._existing or {}
        sub = self._existing_sub
        if sub:
            idx = self.combo_sub.findData(sub)
            if idx >= 0:
                self.combo_sub.setCurrentIndex(idx)
        # Build prefix combo for the locked subcomponent then set ID.
        self._on_subcomponent_changed()
        prefix = id_prefix(tc.get("test_case_id", ""))
        idx = self.combo_prefix.findData(prefix)
        if idx >= 0:
            self.combo_prefix.setCurrentIndex(idx)

        self.lbl_id.setText(tc.get("test_case_id", ""))

        # Lock identification fields.
        self.combo_sub.setEnabled(False)
        self.combo_prefix.setEnabled(False)

        self.txt_name.setText(tc.get("test_name") or "")
        self.txt_description.setPlainText(tc.get("description") or "")
        self.txt_owner.setText(tc.get("owner") or "")
        self.txt_component.setText(tc.get("component") or "")
        self.txt_precondition.setText(tc.get("precondition") or "")

        for combo, value in (
            (self.combo_priority, tc.get("priority")),
            (self.combo_severity, tc.get("severity")),
            (self.combo_readiness, tc.get("automation_readiness")),
            (self.combo_status, tc.get("automation_status")),
            (self.combo_env, tc.get("test_environment_ci_hil")),
        ):
            self._select_combo_value(combo, value)

        self.txt_jira.setText(tc.get("jira_link") or "")

        deps = tc.get("dependency") or []
        self.txt_deps.setText(", ".join(deps))

        steps = tc.get("steps") or []
        self.txt_steps.setPlainText("\n".join(steps))

        self.txt_expected.setText(tc.get("expected_result") or "")
        self.txt_fail.setText(tc.get("fail_conditions") or "")
        self.txt_observations.setText(tc.get("observations") or "")
        self.txt_next.setText(tc.get("next_action_if_fail") or "")

    # ── save ────────────────────────────────────────────────────────────────

    def _build_record(self, test_case_id: str, test_name: str) -> dict:
        deps_text = self.txt_deps.text().strip()
        deps = [d.strip() for d in deps_text.replace("\n", ",").split(",") if d.strip()]

        steps_text = self.txt_steps.toPlainText().strip()
        steps = [line.strip() for line in steps_text.splitlines() if line.strip()]

        return {
            "test_case_id": test_case_id,
            "owner": self._none_if_blank(self.txt_owner.text()),
            "component": self._none_if_blank(self.txt_component.text()),
            "dependency": deps or None,
            "precondition": self._none_if_blank(self.txt_precondition.text()),
            "test_name": test_name,
            "description": self._none_if_blank(self.txt_description.toPlainText()),
            "steps": steps or None,
            "expected_result": self._none_if_blank(self.txt_expected.text()),
            "fail_conditions": self._none_if_blank(self.txt_fail.text()),
            "priority": self._none_if_blank(self.combo_priority.currentData()),
            "severity": self._none_if_blank(self.combo_severity.currentData()),
            "automation_readiness": self._none_if_blank(self.combo_readiness.currentData()),
            "automation_status": self._none_if_blank(self.combo_status.currentData()),
            "test_environment_ci_hil": self._none_if_blank(self.combo_env.currentData()),
            "observations": self._none_if_blank(self.txt_observations.text()),
            "jira_link": self._none_if_blank(self.txt_jira.text()),
            "next_action_if_fail": self._none_if_blank(self.txt_next.text()),
        }

    def _on_save(self) -> None:
        sub = self.combo_sub.currentData()
        prefix = self.combo_prefix.currentData()
        test_name = self.txt_name.text().strip()

        if not sub or not prefix:
            QMessageBox.warning(self, "Validation", "Subcomponent and ID prefix are required.")
            return
        if not test_name:
            QMessageBox.warning(self, "Validation", "Test name is required.")
            return

        yaml_path = REPO_ROOT / self.version / sub / "test_cases.yaml"
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        cases = load_test_cases(yaml_path) if yaml_path.exists() else []

        if self._is_edit:
            tid = (self._existing or {}).get("test_case_id", "")
            updated = self._build_record(tid, test_name)
            for i, c in enumerate(cases):
                if c.get("test_case_id") == tid:
                    cases[i] = updated
                    break
            else:
                QMessageBox.critical(
                    self, "Error",
                    f"Could not locate {tid!r} in {yaml_path.name}; aborting."
                )
                return
        else:
            tid = next_test_id(cases, prefix)
            cases.append(self._build_record(tid, test_name))

        save_test_cases(yaml_path, cases)
        self.accept()

    def _on_delete(self) -> None:
        if not self._is_edit:
            return  # defence: button only shown in edit mode
        tid = (self._existing or {}).get("test_case_id", "")
        sub = self._existing_sub
        if not tid or not sub:
            QMessageBox.critical(
                self, "Error",
                "Cannot delete: test_case_id or subcomponent is missing."
            )
            return
        ok = QMessageBox.question(
            self, "Delete Test Case?",
            f"Permanently remove {tid} from "
            f"{sub}/test_cases.yaml?\n\nThis cannot be undone. "
            "Run records in runs.yaml will NOT be touched.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        yaml_path = REPO_ROOT / self.version / sub / "test_cases.yaml"
        if not yaml_path.exists():
            QMessageBox.critical(self, "Error", f"Cannot find {yaml_path}.")
            return
        cases = load_test_cases(yaml_path)
        new_cases = [c for c in cases if c.get("test_case_id") != tid]
        if len(new_cases) == len(cases):
            QMessageBox.critical(
                self, "Error",
                f"Could not locate {tid!r} in {yaml_path.name}; nothing deleted."
            )
            return
        try:
            save_test_cases(yaml_path, new_cases)
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed",
                                 f"Could not save changes:\n{exc}")
            return
        self.done(self.DELETED)


# Backwards-compatible alias.
AddTestDialog = TestCaseFormDialog


# ═══════════════════════════════════════════════════════════════════════════
#  Run Form Dialog – create one record per selected test case OR edit one
# ═══════════════════════════════════════════════════════════════════════════

class RunFormDialog(QDialog):
    """Execute selected test cases, or edit an existing run record.

    Two modes:
      * **Create** – pass `test_case_ids=[...]`. Selected TC-GUI cases are
        executed and one new run record is appended per ID. Non-executable
        cases are recorded as BLOCKED.
      * **Edit**   – pass `existing_run={...}` plus `existing_index=int`. The
        single record at that position in `runs.yaml` is updated in place.
    """

    def __init__(
        self,
        version: str,
        *,
        test_case_ids: list[str] | None = None,
        existing_run: dict | None = None,
        existing_index: int | None = None,
        prefill_week: str | None = None,
        lock_selection: bool | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.version = version
        self._is_edit = existing_run is not None
        self._existing_run = existing_run
        self._existing_index = existing_index
        self._test_case_ids = list(test_case_ids or [])
        # Default: lock the picker if we're editing an existing run, OR if the
        # caller (e.g. CellRunsDialog) hands us a fixed single test case.
        if lock_selection is None:
            lock_selection = self._is_edit or bool(self._test_case_ids and existing_run is None and len(self._test_case_ids) == 1 and prefill_week is not None)
        self._lock_selection = lock_selection

        self._state = load_runs(version)
        self._weeks: list[str] = list(self._state.get("work_weeks") or DEFAULT_WORK_WEEKS)
        self._all_tids: list[str] = _all_test_case_ids(version)

        if self._is_edit:
            tid = (existing_run or {}).get("test_case_id", "")
            self.setWindowTitle(f"Edit Run – {tid}")
        else:
            self.setWindowTitle("Run Test Cases")
        self.setMinimumSize(620, 540)
        self.resize(720, 640)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(10)

        # ── Header ──────────────────────────────────────────────────────────
        if self._is_edit:
            heading = QLabel(
                f"Editing run for  {(existing_run or {}).get('test_case_id', '')}"
            )
        else:
            heading = QLabel("Execute test-case automation")
        heading.setObjectName("heading")
        outer.addWidget(heading)

        # ── Test-case picker (skipped in edit mode) ─────────────────────────
        self._picker_list: QListWidget | None = None
        if not self._is_edit:
            picker_grp = QGroupBox("Select test case(s) to run")
            pl = QVBoxLayout(picker_grp)
            pl.setSpacing(6)

            top_row = QHBoxLayout()
            self._search = QLineEdit()
            self._search.setPlaceholderText("Filter by ID or name…")
            self._search.textChanged.connect(self._apply_picker_filters)
            top_row.addWidget(self._search, 1)

            btn_select_all = QPushButton("Select All Visible")
            btn_select_all.setObjectName("secondary")
            btn_select_all.clicked.connect(self._on_select_all_visible)
            top_row.addWidget(btn_select_all)

            btn_clear = QPushButton("Clear")
            btn_clear.setObjectName("secondary")
            btn_clear.clicked.connect(self._on_clear_selection)
            top_row.addWidget(btn_clear)
            pl.addLayout(top_row)

            filter_row = QHBoxLayout()
            filter_row.addWidget(QLabel("Automation Status:"))
            self.combo_picker_status = QComboBox()
            self.combo_picker_status.addItem("All", "all")
            self.combo_picker_status.addItem("Ready", "Ready")
            self.combo_picker_status.currentIndexChanged.connect(self._apply_picker_filters)
            filter_row.addWidget(self.combo_picker_status)

            filter_row.addWidget(QLabel("Env:"))
            self.combo_picker_env = QComboBox()
            self.combo_picker_env.addItem("All", "all")
            for env in ("CI", "HIL"):
                self.combo_picker_env.addItem(env, env)
            self.combo_picker_env.currentIndexChanged.connect(self._apply_picker_filters)
            filter_row.addWidget(self.combo_picker_env)
            filter_row.addStretch()
            pl.addLayout(filter_row)

            self._picker_summary = QLabel()
            self._picker_summary.setProperty("role", "fieldLabel")
            self._picker_summary.setWordWrap(False)
            self._picker_summary.setMinimumHeight(20)
            pl.addWidget(self._picker_summary)

            self._picker_list = QListWidget()
            self._picker_list.setMinimumHeight(160)
            self._picker_list.itemChanged.connect(self._on_picker_changed)
            self._populate_picker()
            pl.addWidget(self._picker_list, 1)
            self._update_picker_summary()

            if self._lock_selection and self._test_case_ids:
                self._picker_list.setEnabled(False)
                self._search.setEnabled(False)
                self.combo_picker_status.setEnabled(False)
                self.combo_picker_env.setEnabled(False)
                btn_select_all.setEnabled(False)
                btn_clear.setEnabled(False)

            outer.addWidget(picker_grp)
        else:
            ids_label = QLabel(
                f"Test case: {(existing_run or {}).get('test_case_id', '')}"
            )
            ids_label.setProperty("role", "fieldValue")
            outer.addWidget(ids_label)

        # ── Run-details form ────────────────────────────────────────────────
        form_grp = QGroupBox("Run details")
        form = QFormLayout(form_grp)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.dateChanged.connect(self._on_date_changed)
        form.addRow(self._field_label("Date:"), self.date_edit)

        self.combo_week = QComboBox()
        self.combo_week.addItems(self._weeks)
        form.addRow(self._field_label("Work-week:"), self.combo_week)

        self.combo_result = QComboBox()
        self.combo_result.addItems(RUN_RESULTS)
        if not self._is_edit:
            self.combo_result.setEnabled(False)
            self.combo_result.setToolTip(
                "New run results are filled from automation. Non-executable "
                "test cases are recorded as BLOCKED."
            )
        form.addRow(self._field_label("Result:"), self.combo_result)

        self.txt_executed_by = QLineEdit()
        self.txt_executed_by.setPlaceholderText("Person who ran the test")
        form.addRow(self._field_label("Executed by:"), self.txt_executed_by)

        self.txt_jira = QLineEdit()
        self.txt_jira.setPlaceholderText("https://…")
        form.addRow(self._field_label("Jira link:"), self.txt_jira)

        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText(
            "Optional notes. Automation output is appended to each saved run."
        )
        self.txt_notes.setMinimumHeight(96)
        form.addRow(self._field_label("Notes:"))
        form.addRow(self.txt_notes)

        outer.addWidget(form_grp)
        outer.addStretch()

        # ── Buttons ─────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        self.btn_save = QPushButton(self._save_button_text())
        self.btn_save.setObjectName("success")
        self.btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(self.btn_save)
        outer.addLayout(btn_row)

        # ── Initial values ──────────────────────────────────────────────────
        if self._is_edit and existing_run:
            d = self._parse_date(existing_run.get("date") or "")
            self.date_edit.setDate(QDate(d.year, d.month, d.day))
            wk = existing_run.get("work_week") or ""
            idx = self.combo_week.findText(wk)
            if idx >= 0:
                self.combo_week.setCurrentIndex(idx)
            result = (existing_run.get("result") or "NOT RUN").upper()
            ridx = self.combo_result.findText(result)
            if ridx >= 0:
                self.combo_result.setCurrentIndex(ridx)
            self.txt_executed_by.setText(existing_run.get("executed_by") or "")
            self.txt_jira.setText(existing_run.get("jira_link") or "")
            self.txt_notes.setPlainText(existing_run.get("notes") or "")
        else:
            today = _dt.date.today()
            self.date_edit.setDate(QDate(today.year, today.month, today.day))
            wk = prefill_week or current_work_week(today, self._weeks) or self._weeks[0]
            idx = self.combo_week.findText(wk)
            if idx >= 0:
                self.combo_week.setCurrentIndex(idx)
            self.combo_result.setCurrentText("IN PROGRESS")

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _field_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("role", "fieldLabel")
        return lbl

    @staticmethod
    def _parse_date(text: str) -> _dt.date:
        try:
            return _dt.date.fromisoformat(text[:10])
        except (ValueError, TypeError):
            return _dt.date.today()

    def _save_button_text(self) -> str:
        if self._is_edit:
            return "Save Run"
        n = len(self._picker_selected_ids()) if self._picker_list else len(self._test_case_ids)
        return f"Execute {n} Run{'s' if n != 1 else ''}"

    # ── picker helpers ──────────────────────────────────────────────────────

    def _test_case_meta(self, tid: str) -> dict:
        # Cache picker metadata so text/status/env filters do not re-read YAMLs.
        if not hasattr(self, "_test_case_meta_cache"):
            self._test_case_meta_cache: dict[str, dict] = {}
            for sub in SUBCOMPONENTS:
                p = REPO_ROOT / self.version / sub / "test_cases.yaml"
                if not p.exists():
                    continue
                for tc in load_test_cases(p):
                    test_case_id = tc.get("test_case_id")
                    if test_case_id:
                        self._test_case_meta_cache[test_case_id] = {
                            "subcomponent": sub,
                            "test_name": tc.get("test_name") or "",
                            "description": tc.get("description") or "",
                            "dependency": tc.get("dependency") or [],
                            "automation_status": tc.get("automation_status") or "",
                            "test_environment_ci_hil": tc.get("test_environment_ci_hil") or "",
                        }
        return self._test_case_meta_cache.get(tid, {})

    def _tc_label(self, tid: str) -> str:
        name = self._test_case_meta(tid).get("test_name") or ""
        return f"{tid}    —  {name}" if name else tid

    def _test_case_subcomponent(self, tid: str) -> str | None:
        return self._test_case_meta(tid).get("subcomponent")

    def _is_executable_test_case(self, tid: str) -> bool:
        return self._test_case_subcomponent(tid) == "gui" and tid.startswith("TC-GUI-")

    def _dependency_ids(self, tid: str) -> list[str]:
        deps = self._test_case_meta(tid).get("dependency") or []
        if isinstance(deps, str):
            deps = [part.strip() for part in deps.replace("\n", ",").split(",")]
        return [dep for dep in deps if dep]

    def _with_dependencies(self, tids: list[str]) -> tuple[list[str], list[str]]:
        known_tids = set(self._all_tids)
        seen: set[str] = set()
        missing: list[str] = []
        closure: list[str] = []

        def add_with_deps(tid: str) -> None:
            if tid in seen:
                return
            seen.add(tid)
            for dep in self._dependency_ids(tid):
                if dep in known_tids:
                    add_with_deps(dep)
                elif dep not in missing:
                    missing.append(dep)
            closure.append(tid)

        for tid in tids:
            add_with_deps(tid)
        return self._dependency_priority_order(closure), missing

    def _dependency_priority_order(self, tids: list[str]) -> list[str]:
        """Run dependency-free cases first, then cases whose dependencies passed.

        The executor checks dependency status from the persisted run history, so
        this topological order gives prerequisite cases a chance to record PASS
        before dependent cases execute.
        """
        unique_tids = list(dict.fromkeys(tids))
        pending = set(unique_tids)
        ordered: list[str] = []

        while pending:
            ready = [
                tid
                for tid in unique_tids
                if tid in pending
                and not any(dep in pending for dep in self._dependency_ids(tid))
            ]
            if not ready:
                # Cycle or malformed dependency chain; keep deterministic order
                # rather than blocking the whole run before validation reports it.
                ready = [tid for tid in unique_tids if tid in pending]
            for tid in ready:
                ordered.append(tid)
                pending.remove(tid)

        return ordered

    @staticmethod
    def _combine_run_notes(user_notes: str, detail_notes: str) -> str:
        if user_notes and detail_notes:
            return f"{user_notes}\n\nAutomation output:\n{detail_notes}"
        return detail_notes or user_notes

    def _prompt_multi_run_name(self, run_count: int) -> str | None:
        name, ok = QInputDialog.getText(
            self,
            "Name Multiple Run Tests",
            f"{run_count} tests will run.\n"
            "Optional group name for Timeline delete/search:",
        )
        if not ok:
            return None
        return name.strip()

    def _populate_picker(self) -> None:
        if self._picker_list is None:
            return
        self._picker_list.blockSignals(True)
        try:
            self._picker_list.clear()
            preselected = set(self._test_case_ids)
            for tid in self._all_tids:
                item = QListWidgetItem(self._tc_label(tid))
                item.setData(Qt.ItemDataRole.UserRole, tid)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked if tid in preselected else Qt.CheckState.Unchecked
                )
                self._picker_list.addItem(item)
        finally:
            self._picker_list.blockSignals(False)

    def _picker_selected_ids(self) -> list[str]:
        if self._picker_list is None:
            return list(self._test_case_ids)
        out: list[str] = []
        for i in range(self._picker_list.count()):
            it = self._picker_list.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                out.append(it.data(Qt.ItemDataRole.UserRole))
        return out

    def _apply_picker_filters(self, *_args) -> None:
        if self._picker_list is None:
            return
        needle = self._search.text().strip().lower()
        status_filter = self.combo_picker_status.currentData()
        env_filter = self.combo_picker_env.currentData()
        for i in range(self._picker_list.count()):
            it = self._picker_list.item(i)
            tid = it.data(Qt.ItemDataRole.UserRole)
            meta = self._test_case_meta(tid)
            matches_text = not needle or needle in it.text().lower()
            matches_status = (
                status_filter == "all"
                or meta.get("automation_status") == status_filter
            )
            matches_env = (
                env_filter == "all"
                or meta.get("test_environment_ci_hil") == env_filter
            )
            it.setHidden(not (matches_text and matches_status and matches_env))
        self._update_picker_summary()

    def _on_select_all_visible(self) -> None:
        if self._picker_list is None:
            return
        self._picker_list.blockSignals(True)
        try:
            for i in range(self._picker_list.count()):
                it = self._picker_list.item(i)
                if not it.isHidden():
                    it.setCheckState(Qt.CheckState.Checked)
        finally:
            self._picker_list.blockSignals(False)
        self._on_picker_changed()

    def _on_clear_selection(self) -> None:
        if self._picker_list is None:
            return
        self._picker_list.blockSignals(True)
        try:
            for i in range(self._picker_list.count()):
                self._picker_list.item(i).setCheckState(Qt.CheckState.Unchecked)
        finally:
            self._picker_list.blockSignals(False)
        self._on_picker_changed()

    def _on_picker_changed(self, *_args) -> None:
        self._update_picker_summary()
        if hasattr(self, "btn_save"):
            self.btn_save.setText(self._save_button_text())

    def _update_picker_summary(self) -> None:
        if not hasattr(self, "_picker_summary"):
            return
        n = len(self._picker_selected_ids())
        total = self._picker_list.count() if self._picker_list else 0
        visible = sum(
            1 for i in range(total)
            if self._picker_list and not self._picker_list.item(i).isHidden()
        )
        self._picker_summary.setText(
            f"Selected: {n}/{total} test case{'s' if total != 1 else ''}  |  "
            f"Visible with filters: {visible}"
        )

    def _on_date_changed(self, qdate: QDate) -> None:
        # Auto-snap the work-week dropdown to whatever WW the date falls in
        # (only if it's in our valid range — otherwise leave the user's choice).
        py_date = _dt.date(qdate.year(), qdate.month(), qdate.day())
        wk = current_work_week(py_date, self._weeks)
        if wk:
            idx = self.combo_week.findText(wk)
            if idx >= 0 and idx != self.combo_week.currentIndex():
                self.combo_week.setCurrentIndex(idx)

    # ── save ────────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        date_text = self.date_edit.date().toString("yyyy-MM-dd")
        week = self.combo_week.currentText().strip()
        result = self.combo_result.currentText().strip().upper()
        executed_by = self.txt_executed_by.text().strip()
        jira = self.txt_jira.text().strip()
        notes = self.txt_notes.toPlainText().strip()

        if not week:
            QMessageBox.warning(self, "Validation", "A work-week is required.")
            return
        if self._is_edit and result not in RUN_RESULTS:
            QMessageBox.warning(self, "Validation",
                                f"Result must be one of: {', '.join(RUN_RESULTS)}.")
            return

        runs: list[dict] = list(self._state.get("runs") or [])
        execution_results: list[tuple[str, str]] | None = None

        if self._is_edit:
            if self._existing_index is None or not (0 <= self._existing_index < len(runs)):
                QMessageBox.critical(self, "Error",
                                     "Could not locate the run record to edit.")
                return
            existing = dict(runs[self._existing_index])
            existing.update({
                "date":        date_text,
                "work_week":   week,
                "result":      result,
                "notes":       notes,
                "jira_link":   jira,
                "executed_by": executed_by,
            })
            runs[self._existing_index] = existing
        else:
            selected_tids = self._picker_selected_ids()
            if not selected_tids:
                QMessageBox.warning(
                    self, "No Test Cases Selected",
                    "Tick at least one test case in the picker before saving."
                )
                return
            tids, missing_dependencies = self._with_dependencies(selected_tids)
            if missing_dependencies:
                QMessageBox.warning(
                    self,
                    "Missing Dependencies",
                    "These dependency test cases were not found and will not run:\n"
                    + ", ".join(missing_dependencies),
                )
            run_name = ""
            if len(tids) > 1:
                prompt_result = self._prompt_multi_run_name(len(tids))
                if prompt_result is None:
                    return
                run_name = prompt_result
            now = _dt.datetime.now().isoformat(timespec="seconds")
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                execution_results = []
                for tid in tids:
                    if self._is_executable_test_case(tid):
                        try:
                            execution = run_case(
                                self.version,
                                tid,
                                executed_by=executed_by,
                                record=False,
                            )
                            run_result = execution.result
                            run_notes = self._combine_run_notes(notes, execution.notes)
                            duration_seconds = execution.duration_seconds
                        except Exception as exc:
                            run_result = "FAIL"
                            run_notes = self._combine_run_notes(
                                notes,
                                f"Automation failed before producing a result: {exc}",
                            )
                            duration_seconds = None
                    else:
                        run_result = "BLOCKED"
                        run_notes = self._combine_run_notes(
                            notes,
                            "Automation unavailable: only TC-GUI cases can be "
                            "executed automatically.",
                        )
                        duration_seconds = None
                    execution_results.append((tid, run_result))
                    run_record = {
                        "id":           uuid.uuid4().hex[:12],
                        "test_case_id": tid,
                        "date":         date_text,
                        "work_week":    week,
                        "result":       run_result,
                        "notes":        run_notes,
                        "jira_link":    jira,
                        "executed_by":  executed_by,
                        "created_at":   now,
                    }
                    if run_name:
                        run_record["run_name"] = run_name
                    duration = _coerce_duration_seconds(duration_seconds)
                    if duration is not None:
                        run_record["duration_seconds"] = duration
                    runs.append(run_record)
                    self._state["runs"] = runs
                    try:
                        save_runs(self.version, self._state)
                    except Exception as exc:
                        QMessageBox.critical(
                            self,
                            "Save Failed",
                            f"Could not save run for {tid}:\n{exc}",
                        )
                        return
            finally:
                QApplication.restoreOverrideCursor()

        if self._is_edit:
            self._state["runs"] = runs
            try:
                save_runs(self.version, self._state)
            except Exception as exc:
                QMessageBox.critical(self, "Save Failed",
                                     f"Could not save runs:\n{exc}")
                return
        if execution_results is not None:
            summary = ", ".join(
                f"{tid}: {run_result}" for tid, run_result in execution_results
            )
            QMessageBox.information(
                self,
                "Automation Complete",
                f"Recorded {len(execution_results)} run record"
                f"{'s' if len(execution_results) != 1 else ''}.\n\n{summary}",
            )
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════
#  Cell Runs Dialog – list runs in a single (test_case, work_week) cell
# ═══════════════════════════════════════════════════════════════════════════

class CellRunsDialog(QDialog):
    """Compact list of all runs in a single timeline cell, with per-row
    Edit / Delete buttons and an Add Run button."""

    def __init__(self, version: str, tid: str, week: str, parent=None):
        super().__init__(parent)
        self.version = version
        self.tid = tid
        self.week = week
        self.changed = False  # parent uses this to know when to refresh

        self.setWindowTitle(f"{tid}  •  {week}")
        self.setMinimumSize(640, 360)
        self.resize(720, 420)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(10)

        heading = QLabel(f"Runs for {tid} in {week}")
        heading.setObjectName("heading")
        outer.addWidget(heading)

        sub = QLabel("Most recent at the top. Use Edit to fix a record, "
                     "Delete to remove one, or Add Run to log another attempt.")
        sub.setProperty("role", "fieldLabel")
        sub.setWordWrap(True)
        outer.addWidget(sub)

        self._scroll_inner = QWidget()
        self._scroll_inner.setObjectName("dialogContent")
        self._scroll_inner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._list_layout = QVBoxLayout(self._scroll_inner)
        self._list_layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.viewport().setStyleSheet("background-color: #1e1e2e;")
        scroll.setWidget(self._scroll_inner)
        outer.addWidget(scroll, 1)

        bottom = QHBoxLayout()
        btn_add = QPushButton("＋  Add Run")
        btn_add.setObjectName("success")
        btn_add.clicked.connect(self._on_add)
        bottom.addWidget(btn_add)
        bottom.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setObjectName("secondary")
        btn_close.clicked.connect(self.accept)
        bottom.addWidget(btn_close)
        outer.addLayout(bottom)

        self._rebuild_list()

    # ── list rendering ──────────────────────────────────────────────────────

    def _rebuild_list(self) -> None:
        # Clear existing widgets.
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        state = load_runs(self.version)
        runs = state.get("runs") or []

        # Pair each cell-matching run with its index in the master list so we
        # can edit/delete it precisely later.
        cell_runs = [
            (idx, r) for idx, r in enumerate(runs)
            if r.get("test_case_id") == self.tid and r.get("work_week") == self.week
        ]
        cell_runs.sort(
            key=lambda pair: (pair[1].get("date") or "", pair[1].get("created_at") or ""),
            reverse=True,
        )

        if not cell_runs:
            empty = QLabel("No runs recorded for this cell yet.")
            empty.setProperty("role", "fieldValueEmpty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._list_layout.addWidget(empty)
            self._list_layout.addStretch()
            return

        for idx, run in cell_runs:
            self._list_layout.addWidget(self._make_run_row(idx, run))
        self._list_layout.addStretch()

    def _make_run_row(self, run_index: int, run: dict) -> QFrame:
        row = QFrame()
        row.setStyleSheet(
            "QFrame { background-color: #181825; border: 1px solid #313244;"
            " border-radius: 6px; }"
        )
        rl = QHBoxLayout(row)
        rl.setContentsMargins(10, 8, 10, 8)
        rl.setSpacing(10)

        # Result chip (color tinted).
        result = run.get("result") or "NOT RUN"
        bg, fg = RUN_RESULT_COLORS.get(result, ("#2a2a3a", "#cdd6f4"))
        chip = QLabel(result)
        chip.setStyleSheet(
            f"background-color: {bg}; color: {fg};"
            " border: none; border-radius: 4px; padding: 4px 10px;"
            " font-weight: bold;"
        )
        chip.setMinimumWidth(110)
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rl.addWidget(chip)

        # Body: date + meta + notes.
        body = QVBoxLayout()
        body.setSpacing(2)
        date_line = QLabel(
            f"{run.get('date') or '(no date)'}"
            f"   •   {run.get('executed_by') or '(no executor)'}"
            + (
                f"   •   {format_duration(run.get('duration_seconds'))}"
                if format_duration(run.get("duration_seconds"))
                else ""
            )
        )
        date_line.setProperty("role", "fieldValue")
        body.addWidget(date_line)
        run_name = run.get("run_name") or ""
        if run_name:
            name_line = QLabel(f"Run group: {run_name}")
            name_line.setProperty("role", "fieldValue")
            body.addWidget(name_line)
        notes = run.get("notes") or ""
        jira = run.get("jira_link") or ""
        detail_text = notes
        if jira:
            detail_text = f"{notes}   ({jira})" if notes else jira
        notes_lbl = QLabel(detail_text or "(no notes)")
        notes_lbl.setWordWrap(True)
        notes_lbl.setProperty(
            "role", "fieldValueEmpty" if not detail_text else "fieldValue"
        )
        notes_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        body.addWidget(notes_lbl)
        rl.addLayout(body, 1)

        # Edit / Delete buttons (text labels, not glyphs).
        btn_col = QVBoxLayout()
        btn_col.setSpacing(4)
        btn_edit = QPushButton("Edit")
        btn_edit.setObjectName("secondary")
        btn_edit.setMinimumWidth(80)
        btn_edit.setToolTip("Edit this run record (date, week, result, notes)")
        btn_edit.clicked.connect(lambda _=False, i=run_index, r=run: self._on_edit(i, r))
        btn_col.addWidget(btn_edit)

        btn_del = QPushButton("Delete")
        btn_del.setObjectName("danger")
        btn_del.setStyleSheet(DANGER_BUTTON_STYLE)
        btn_del.setMinimumWidth(80)
        btn_del.setToolTip("Permanently remove this run record from runs.yaml")
        btn_del.clicked.connect(lambda _=False, i=run_index, r=run: self._on_delete(i, r))
        btn_col.addWidget(btn_del)
        rl.addLayout(btn_col)

        return row

    # ── actions ─────────────────────────────────────────────────────────────

    def _on_add(self) -> None:
        dlg = RunFormDialog(
            self.version,
            test_case_ids=[self.tid],
            prefill_week=self.week,
            lock_selection=True,
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.changed = True
            self._rebuild_list()

    def _on_edit(self, run_index: int, run: dict) -> None:
        dlg = RunFormDialog(
            self.version,
            existing_run=run,
            existing_index=run_index,
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.changed = True
            self._rebuild_list()

    def _on_delete(self, run_index: int, run: dict) -> None:
        ok = QMessageBox.question(
            self, "Delete Run?",
            f"Delete the {run.get('result')} run for {run.get('test_case_id')} "
            f"on {run.get('date') or '(no date)'}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        state = load_runs(self.version)
        runs = list(state.get("runs") or [])
        if 0 <= run_index < len(runs):
            del runs[run_index]
            state["runs"] = runs
            try:
                save_runs(self.version, state)
            except Exception as exc:
                QMessageBox.critical(self, "Save Failed",
                                     f"Could not save runs:\n{exc}")
                return
            self.changed = True
            self._rebuild_list()


class FrozenFirstColumnTableView(QTableView):
    """QTableView with an Excel-like frozen first column."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frozen_view = QTableView(self)
        self._frozen_column_width = 140
        self._frozen_margin_width = -1
        self._configure_frozen_view()

        self.viewport().stackUnder(self._frozen_view)
        self.horizontalHeader().sectionResized.connect(self._on_section_resized)
        self.verticalHeader().sectionResized.connect(self._update_frozen_geometry)
        self.verticalScrollBar().valueChanged.connect(
            self._frozen_view.verticalScrollBar().setValue
        )
        self._frozen_view.verticalScrollBar().valueChanged.connect(
            self.verticalScrollBar().setValue
        )
        self._frozen_view.clicked.connect(lambda index: self.clicked.emit(index))
        self._frozen_view.doubleClicked.connect(
            lambda index: self.doubleClicked.emit(index)
        )

    def setModel(self, model) -> None:
        super().setModel(model)
        self._frozen_view.setModel(model)
        if self.selectionModel() is not None:
            self._frozen_view.setSelectionModel(self.selectionModel())
        self.refresh_frozen_columns()

    def setColumnWidth(self, column: int, width: int) -> None:
        super().setColumnWidth(column, width)
        if column == 0:
            self._frozen_column_width = width
            self._frozen_view.setColumnWidth(column, width)
            self._update_frozen_geometry()

    def setRowHeight(self, row: int, height: int) -> None:
        super().setRowHeight(row, height)
        self._frozen_view.setRowHeight(row, height)

    def setVerticalScrollMode(self, mode) -> None:
        super().setVerticalScrollMode(mode)
        self._frozen_view.setVerticalScrollMode(mode)

    def setHorizontalScrollMode(self, mode) -> None:
        super().setHorizontalScrollMode(mode)
        self._frozen_view.setHorizontalScrollMode(mode)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_frozen_geometry()

    def updateGeometries(self) -> None:
        super().updateGeometries()
        self._update_frozen_geometry()

    def scrollTo(self, index, hint=QAbstractItemView.ScrollHint.EnsureVisible) -> None:
        if index.column() > 0:
            super().scrollTo(index, hint)

    def refresh_frozen_columns(self) -> None:
        model = self.model()
        if model is None:
            return
        self.setColumnHidden(0, False)
        self._frozen_column_width = self.columnWidth(0)
        for column in range(model.columnCount()):
            self._frozen_view.setColumnHidden(column, column != 0)
        self._frozen_view.setColumnWidth(0, self._frozen_column_width)
        self._update_frozen_geometry()

    def _configure_frozen_view(self) -> None:
        self._frozen_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._frozen_view.setAutoFillBackground(True)
        self._frozen_view.viewport().setAutoFillBackground(True)
        self._frozen_view.setFrameShape(QFrame.Shape.NoFrame)
        self._frozen_view.verticalHeader().setVisible(False)
        self._frozen_view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._frozen_view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._frozen_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._frozen_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._frozen_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._frozen_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems
        )
        self._frozen_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._frozen_view.setAlternatingRowColors(True)
        self._frozen_view.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Fixed
        )
        self._frozen_view.horizontalHeader().setSectionsClickable(False)
        self._frozen_view.setStyleSheet(
            "QTableView {"
            "  background-color: #181825;"
            "  border: none;"
            "  border-right: 1px solid #45475a;"
            "}"
            "QTableView::item { background-color: #1e1e2e; }"
        )
        self._frozen_view.show()

    def _on_section_resized(self, logical_index: int, _old_size: int, new_size: int) -> None:
        if logical_index == 0:
            self._frozen_column_width = new_size
            self._frozen_view.setColumnWidth(0, new_size)
        self._update_frozen_geometry()

    def _update_frozen_geometry(self) -> None:
        width = self.columnWidth(0)
        self._frozen_column_width = width
        if width != self._frozen_margin_width:
            self._frozen_margin_width = width
            self.setViewportMargins(width, 0, 0, 0)
        self._frozen_view.horizontalHeader().setFixedHeight(
            self.horizontalHeader().height()
        )
        self._frozen_view.setGeometry(
            self.frameWidth(),
            self.frameWidth(),
            width,
            self.viewport().height() + self.horizontalHeader().height(),
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Timeline Dialog – view-only week-by-week schedule grid
# ═══════════════════════════════════════════════════════════════════════════

class TimelineDialog(QDialog):
    """Read-only timeline grid: rows are test cases, columns are work-weeks.

    Cells display the **latest** run result for that (test case, week) pair,
    colour-coded by result. Clicking a populated cell opens
    :class:`CellRunsDialog`, where individual runs can be edited or deleted.
    Empty cells open the same dialog so the user can add a run.

    All persistence happens via the Run dialog flow (:class:`RunFormDialog`)
    and the cell editor — the Timeline itself never writes data.
    """

    EMPTY_TINT     = QColor("#181825")
    ID_TEXT_COLOR  = QColor("#89b4fa")

    def __init__(self, version: str, parent=None):
        super().__init__(parent)
        self.version = version
        self.setWindowTitle(f"Timeline – {version.replace('_', ' ').title()}  (view-only)")
        self.setMinimumSize(900, 480)
        self.resize(1280, 640)

        self._reload_state()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        # ── Header line 1: title + status ───────────────────────────────────
        title_row = QHBoxLayout()
        title = QLabel(f"Validation Timeline  •  {version.replace('_', ' ').title()}")
        title.setObjectName("heading")
        title_row.addWidget(title)
        title_row.addStretch()
        self.lbl_status = QLabel(self._status_text())
        self.lbl_status.setProperty("role", "fieldLabel")
        title_row.addWidget(self.lbl_status)
        outer.addLayout(title_row)

        # ── Header line 2: year + computed metrics ──────────────────────────
        summary_row = QHBoxLayout()
        summary_row.setSpacing(20)

        self.lbl_year = QLabel(self._year_text())
        self.lbl_year.setStyleSheet(
            "color: #f9e2af; font-weight: bold; font-size: 13px;"
        )
        summary_row.addWidget(self.lbl_year)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #45475a;")
        summary_row.addWidget(sep)

        self.metric_value_lbls: dict[str, QLabel] = {}
        for label in METRIC_LABELS:
            cell_lbl = QLabel(label + ":")
            cell_lbl.setProperty("role", "fieldLabel")
            summary_row.addWidget(cell_lbl)
            value_lbl = QLabel("0%")
            value_lbl.setStyleSheet(
                "color: #cdd6f4; font-weight: bold; font-size: 13px;"
            )
            summary_row.addWidget(value_lbl)
            self.metric_value_lbls[label] = value_lbl

        total_time_lbl = QLabel("Total Time Taken:")
        total_time_lbl.setProperty("role", "fieldLabel")
        summary_row.addWidget(total_time_lbl)
        self.lbl_total_time = QLabel("0s")
        self.lbl_total_time.setStyleSheet(
            "color: #cdd6f4; font-weight: bold; font-size: 13px;"
        )
        summary_row.addWidget(self.lbl_total_time)
        summary_row.addStretch()
        outer.addLayout(summary_row)

        hint = QLabel(
            "Click a Test Case ID to view details. Double-click any result cell "
            "to view, edit or delete its run records. New runs are created from "
            "the main window's ▶ Run button."
        )
        hint.setProperty("role", "fieldLabel")
        hint.setWordWrap(True)
        outer.addWidget(hint)

        # ── Named run-group filter ──────────────────────────────────────────
        group_filter = QGroupBox("Named Multiple Run")
        gfl = QHBoxLayout(group_filter)
        gfl.setSpacing(8)

        group_hint = QLabel("Filter by name:")
        group_hint.setProperty("role", "fieldLabel")
        gfl.addWidget(group_hint)

        self._group_filter_list = QListWidget()
        self._group_filter_list.setMinimumHeight(44)
        self._group_filter_list.setMaximumHeight(64)
        self._group_filter_list.itemChanged.connect(self._on_run_group_filter_changed)
        gfl.addWidget(self._group_filter_list, 1)

        group_buttons = QHBoxLayout()
        group_buttons.setSpacing(4)
        btn_select_groups = QPushButton("Select All Names")
        btn_select_groups.setObjectName("secondary")
        btn_select_groups.clicked.connect(self._select_all_run_groups)
        group_buttons.addWidget(btn_select_groups)
        btn_clear_groups = QPushButton("Show All")
        btn_clear_groups.setObjectName("secondary")
        btn_clear_groups.clicked.connect(self._clear_run_group_filter)
        group_buttons.addWidget(btn_clear_groups)
        btn_delete_group = QPushButton("Delete Run Group")
        btn_delete_group.setObjectName("danger")
        btn_delete_group.setStyleSheet(DANGER_BUTTON_STYLE)
        btn_delete_group.setToolTip("Delete all timeline run records with the selected run group name.")
        btn_delete_group.clicked.connect(self._on_delete_run_group)
        group_buttons.addWidget(btn_delete_group)
        gfl.addLayout(group_buttons)
        outer.addWidget(group_filter)
        self._populate_run_group_filter()

        # ── Table ───────────────────────────────────────────────────────────
        self.model = QStandardItemModel()
        self.table = FrozenFirstColumnTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(False)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.verticalHeader().setVisible(False)
        self.table.clicked.connect(self._on_click)
        self.table.doubleClicked.connect(self._on_double_click)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(False)
        outer.addWidget(self.table, 1)
        self._build_model()

        # ── Bottom bar (no Save) ────────────────────────────────────────────
        bottom = QHBoxLayout()
        btn_refresh = QPushButton("↻  Refresh")
        btn_refresh.setObjectName("secondary")
        btn_refresh.setToolTip("Reload runs.yaml from disk.")
        btn_refresh.clicked.connect(self._on_refresh)
        bottom.addWidget(btn_refresh)
        btn_export = QPushButton("Export CSV")
        btn_export.setObjectName("secondary")
        btn_export.setToolTip(
            f"Export populated {version.replace('_', ' ').title()} Timeline results to CSV."
        )
        btn_export.clicked.connect(self._on_export_csv)
        bottom.addWidget(btn_export)
        bottom.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setObjectName("secondary")
        btn_close.clicked.connect(self.accept)
        bottom.addWidget(btn_close)
        outer.addLayout(bottom)

    # ── data ────────────────────────────────────────────────────────────────

    def _reload_state(self) -> None:
        self._state = load_runs(self.version)
        self._weeks: list[str] = list(self._state.get("work_weeks") or DEFAULT_WORK_WEEKS)
        self._tids: list[str] = _all_test_case_ids(self.version)
        self._runs: list[dict] = list(self._state.get("runs") or [])
        self._test_cases_by_id = self._load_test_cases_by_id()

    def _load_test_cases_by_id(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        automate_dir = REPO_ROOT / self.version
        for sub, path in discover_test_files(automate_dir).items():
            for tc in load_test_cases(path):
                tid = tc.get("test_case_id")
                if tid:
                    row = dict(tc)
                    row["__subcomponent"] = sub
                    out[tid] = row
        return out

    def _status_text(self) -> str:
        display_runs = self._display_runs()
        display_tids = self._display_tids(display_runs)
        selected_groups = self._selected_run_groups()
        run_text = f"{len(display_runs)} run record{'s' if len(display_runs) != 1 else ''}"
        if selected_groups:
            run_text = (
                f"{len(display_runs)} of {len(self._runs)} run record"
                f"{'s' if len(self._runs) != 1 else ''} shown"
            )
        return (
            f"{len(display_tids)} test cases × {len(self._weeks)} work-weeks  •  "
            f"{run_text}"
        )

    def _year_text(self) -> str:
        return f"Year: {self._state.get('year') or _dt.date.today().year}"

    def _run_group_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for run in self._runs:
            run_name = (run.get("run_name") or "").strip()
            if run_name:
                counts[run_name] = counts.get(run_name, 0) + 1
        return counts

    def _run_group_duration_totals(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for run in self._runs:
            run_name = (run.get("run_name") or "").strip()
            if not run_name:
                continue
            seconds = _coerce_duration_seconds(run.get("duration_seconds"))
            if seconds is not None:
                totals[run_name] = totals.get(run_name, 0.0) + seconds
        return totals

    def _run_group_result_counts(self) -> dict[str, dict[str, int]]:
        counts: dict[str, dict[str, int]] = {}
        for run in self._runs:
            run_name = (run.get("run_name") or "").strip()
            if not run_name:
                continue
            result = (run.get("result") or "NOT RUN").strip().upper()
            group_counts = counts.setdefault(run_name, {"PASS": 0, "BLOCKED": 0, "FAIL": 0})
            if result in group_counts:
                group_counts[result] += 1
        return counts

    def _selected_run_groups(self) -> set[str]:
        if not hasattr(self, "_group_filter_list"):
            return set()
        selected: set[str] = set()
        for i in range(self._group_filter_list.count()):
            item = self._group_filter_list.item(i)
            name = item.data(Qt.ItemDataRole.UserRole)
            if name and item.checkState() == Qt.CheckState.Checked:
                selected.add(name)
        return selected

    def _display_runs(self) -> list[dict]:
        selected_groups = self._selected_run_groups()
        if not selected_groups:
            return list(self._runs)
        return [
            run for run in self._runs
            if (run.get("run_name") or "").strip() in selected_groups
        ]

    def _display_tids(self, display_runs: list[dict]) -> list[str]:
        if not self._selected_run_groups():
            return list(self._tids)
        visible_tids = {
            run.get("test_case_id") for run in display_runs
            if run.get("test_case_id")
        }
        return [tid for tid in self._tids if tid in visible_tids]

    def _populate_run_group_filter(self, keep_selection: set[str] | None = None) -> None:
        if not hasattr(self, "_group_filter_list"):
            return
        if keep_selection is None:
            keep_selection = self._selected_run_groups()

        group_counts = self._run_group_counts()
        group_duration_totals = self._run_group_duration_totals()
        group_result_counts = self._run_group_result_counts()
        self._group_filter_list.blockSignals(True)
        try:
            self._group_filter_list.clear()
            if not group_counts:
                item = QListWidgetItem("(no named multiple-test runs)")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                self._group_filter_list.addItem(item)
                return

            for name, count in sorted(group_counts.items(), key=lambda item: item[0].casefold()):
                total_time = format_duration(group_duration_totals.get(name, 0.0))
                result_counts = group_result_counts.get(
                    name,
                    {"PASS": 0, "BLOCKED": 0, "FAIL": 0},
                )
                item = QListWidgetItem(
                    f"{name} ({count} record{'s' if count != 1 else ''}, "
                    f"PASS {result_counts['PASS']}, "
                    f"BLOCK {result_counts['BLOCKED']}, "
                    f"FAIL {result_counts['FAIL']}, "
                    f"total {total_time})"
                )
                item.setData(Qt.ItemDataRole.UserRole, name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked
                    if name in keep_selection
                    else Qt.CheckState.Unchecked
                )
                self._group_filter_list.addItem(item)
        finally:
            self._group_filter_list.blockSignals(False)

    def _on_run_group_filter_changed(self, *_args) -> None:
        self._build_model()
        self.lbl_status.setText(self._status_text())

    def _set_all_run_groups_checked(self, checked: bool) -> None:
        if not hasattr(self, "_group_filter_list"):
            return
        self._group_filter_list.blockSignals(True)
        try:
            for i in range(self._group_filter_list.count()):
                item = self._group_filter_list.item(i)
                if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                    item.setCheckState(
                        Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                    )
        finally:
            self._group_filter_list.blockSignals(False)
        self._on_run_group_filter_changed()

    def _select_all_run_groups(self) -> None:
        self._set_all_run_groups_checked(True)

    def _clear_run_group_filter(self) -> None:
        self._set_all_run_groups_checked(False)

    # ── table build ─────────────────────────────────────────────────────────

    def _build_model(self) -> None:
        self.model.clear()
        self.model.setHorizontalHeaderLabels(["Test Case ID", *self._weeks])

        display_runs = self._display_runs()
        display_tids = self._display_tids(display_runs)
        for tid in display_tids:
            row = self._make_row(tid, display_runs)
            self.model.appendRow(row)

        self.table.setColumnWidth(0, 140)
        for row in range(self.model.rowCount()):
            self.table.setRowHeight(row, 46)
        for col in range(1, self.model.columnCount()):
            self.table.setColumnWidth(col, 110)
        self.table.refresh_frozen_columns()

        self._refresh_metric_labels()

    def _make_row(self, tid: str, display_runs: list[dict]) -> list[QStandardItem]:
        head = QStandardItem(tid)
        head.setEditable(False)
        head.setForeground(self.ID_TEXT_COLOR)
        f = head.font()
        f.setBold(True)
        head.setFont(f)
        head.setData({"tid": tid, "week": None}, Qt.ItemDataRole.UserRole)

        items: list[QStandardItem] = [head]
        for week in self._weeks:
            cell = QStandardItem("")
            cell.setEditable(False)
            cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.setData({"tid": tid, "week": week}, Qt.ItemDataRole.UserRole)

            cell_runs = runs_for_cell(display_runs, tid, week)
            if cell_runs:
                latest = cell_runs[0]
                result = latest.get("result") or "NOT RUN"
                count = len(cell_runs)
                text = result if count == 1 else f"{result} ×{count}"
                duration_text = format_duration(latest.get("duration_seconds"))
                if duration_text:
                    text = f"{text}\n{duration_text}"
                bg, fg = RUN_RESULT_COLORS.get(result, ("#2a2a3a", "#cdd6f4"))
                cell.setText(text)
                cell.setBackground(QColor(bg))
                cell.setForeground(QColor(fg))
                font = cell.font()
                font.setBold(True)
                cell.setFont(font)
                tip_lines = [
                    f"{r.get('date') or '(no date)'}  ·  {r.get('result')}"
                    + (
                        f"  ·  {format_duration(r.get('duration_seconds'))}"
                        if format_duration(r.get("duration_seconds"))
                        else ""
                    )
                    + (f"  ·  {r.get('notes')}" if r.get("notes") else "")
                    + (f"  ·  Group: {r.get('run_name')}" if r.get("run_name") else "")
                    for r in cell_runs
                ]
                cell.setToolTip("\n".join(tip_lines))
            else:
                cell.setBackground(self.EMPTY_TINT)
            items.append(cell)
        return items

    def _refresh_metric_labels(self) -> None:
        display_runs = self._display_runs()
        metrics = compute_run_metrics(display_runs, self._display_tids(display_runs))
        for label, value_lbl in self.metric_value_lbls.items():
            value_lbl.setText(metrics.get(label, "0%"))
        self.lbl_total_time.setText(format_total_duration(display_runs))
        # Color-tint each value to mirror the run-result palette.
        self.metric_value_lbls["% PASS"].setStyleSheet(
            "color: #a6e3a1; font-weight: bold; font-size: 13px;"
        )
        self.metric_value_lbls["% FAIL"].setStyleSheet(
            "color: #f38ba8; font-weight: bold; font-size: 13px;"
        )
        self.metric_value_lbls["% NOT RUN"].setStyleSheet(
            "color: #a6adc8; font-weight: bold; font-size: 13px;"
        )

    # ── interactions ────────────────────────────────────────────────────────

    def _on_click(self, index) -> None:
        if not index.isValid() or index.column() != 0:
            return
        item = self.model.itemFromIndex(index)
        if item is None:
            return
        meta = item.data(Qt.ItemDataRole.UserRole) or {}
        tid = meta.get("tid")
        if tid:
            self._open_test_case_detail(tid)

    def _open_test_case_detail(self, tid: str) -> None:
        tc = self._test_cases_by_id.get(tid)
        if not tc:
            QMessageBox.information(
                self,
                "Test Case Not Found",
                f"Could not find details for {tid}.",
            )
            return

        dlg = DetailDialog(tc, self)
        result = dlg.exec()
        if result != DetailDialog.EDIT_REQUESTED:
            return

        sub = tc.get("__subcomponent")
        if not sub:
            QMessageBox.critical(
                self,
                "Error",
                "Cannot determine which subcomponent file owns this test case.",
            )
            return
        edit_dlg = TestCaseFormDialog(
            self.version,
            existing_tc=tc,
            existing_subcomponent=sub,
            parent=self,
        )
        edit_result = edit_dlg.exec()
        if edit_result in (QDialog.DialogCode.Accepted, TestCaseFormDialog.DELETED):
            self._on_refresh()

    def _on_double_click(self, index) -> None:
        if not index.isValid():
            return
        item = self.model.itemFromIndex(index)
        if item is None:
            return
        meta = item.data(Qt.ItemDataRole.UserRole) or {}
        tid = meta.get("tid")
        week = meta.get("week")
        if not tid or not week:
            return  # double-clicked the ID column – nothing to do
        dlg = CellRunsDialog(self.version, tid, week, parent=self)
        dlg.exec()
        if dlg.changed:
            self._on_refresh()

    def _on_refresh(self) -> None:
        selected_groups = self._selected_run_groups()
        self._reload_state()
        self._populate_run_group_filter(selected_groups)
        self._build_model()
        self.lbl_status.setText(self._status_text())
        self.lbl_year.setText(self._year_text())

    def _on_delete_run_group(self) -> None:
        group_counts = self._run_group_counts()
        if not group_counts:
            QMessageBox.information(
                self,
                "No Named Run Groups",
                "There are no named multiple-run groups to delete.",
            )
            return

        choices = [
            f"{name} ({count} record{'s' if count != 1 else ''})"
            for name, count in sorted(group_counts.items(), key=lambda item: item[0].casefold())
        ]
        choice, ok = QInputDialog.getItem(
            self,
            "Delete Run Group",
            "Choose a named multiple-run group to delete from the Timeline:",
            choices,
            0,
            False,
        )
        if not ok or not choice:
            return

        run_name = choice.rsplit(" (", 1)[0]
        record_count = group_counts.get(run_name, 0)
        confirm = QMessageBox.question(
            self,
            "Delete Run Group?",
            f"Delete all {record_count} run record"
            f"{'s' if record_count != 1 else ''} named {run_name!r}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        state = load_runs(self.version)
        runs = list(state.get("runs") or [])
        state["runs"] = [
            run for run in runs
            if (run.get("run_name") or "").strip() != run_name
        ]
        try:
            save_runs(self.version, state)
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", f"Could not save runs:\n{exc}")
            return

        self._on_refresh()
        QMessageBox.information(
            self,
            "Run Group Deleted",
            f"Deleted {record_count} run record"
            f"{'s' if record_count != 1 else ''} named {run_name!r}.",
        )

    def _on_export_csv(self) -> None:
        output_path = REPO_ROOT / f"{self.version}_results.csv"
        try:
            output = io.StringIO()
            headers = [
                "Test Case ID",
                "Work Week",
                "Date",
                "Result",
                "Run Group",
                "Time Taken",
                "Notes",
                "Jira Link",
                "Executed By",
            ]
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            display_runs = self._display_runs()
            display_tids = self._display_tids(display_runs)
            for tid in display_tids:
                for week in self._weeks:
                    latest = latest_run_for_cell(display_runs, tid, week)
                    if latest is None:
                        continue
                    writer.writerow({
                        "Test Case ID": latest.get("test_case_id") or tid,
                        "Work Week": latest.get("work_week") or week,
                        "Date": latest.get("date") or "",
                        "Result": latest.get("result") or "",
                        "Run Group": latest.get("run_name") or "",
                        "Time Taken": format_duration(latest.get("duration_seconds")),
                        "Notes": latest.get("notes") or "",
                        "Jira Link": latest.get("jira_link") or "",
                        "Executed By": latest.get("executed_by") or "",
                    })
            output_path.write_text(
                output.getvalue(),
                encoding="utf-8",
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Export CSV Failed",
                f"Could not write CSV report to:\n{output_path}\n\n{exc}",
            )
            return

        QMessageBox.information(
            self,
            "CSV Export Complete",
            f"CSV report written to:\n{output_path}",
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Main Window
# ═══════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Automate Stack Validation")
        self.setMinimumSize(1180, 660)
        self.resize(1320, 740)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # ── Top bar ─────────────────────────────────────────────────────────
        top_bar = QHBoxLayout()

        title = QLabel("Automate Stack Validation")
        title.setObjectName("heading")
        top_bar.addWidget(title)
        top_bar.addStretch()

        top_bar.addWidget(QLabel("Version:"))
        self.combo_version = QComboBox()
        for v in discover_versions():
            self.combo_version.addItem(v.replace("_", " ").title(), v)
        self.combo_version.currentIndexChanged.connect(self._reload)
        top_bar.addWidget(self.combo_version)

        root.addLayout(top_bar)

        # ── Filter bar ──────────────────────────────────────────────────────
        filter_bar = QHBoxLayout()

        filter_bar.addWidget(QLabel("Subcomponent:"))
        self.combo_filter_sub = QComboBox()
        self.combo_filter_sub.addItem("All", "all")
        for s in SUBCOMPONENTS:
            self.combo_filter_sub.addItem(DISPLAY_NAMES[s], s)
        self.combo_filter_sub.currentIndexChanged.connect(self._apply_filters)
        filter_bar.addWidget(self.combo_filter_sub)

        filter_bar.addWidget(QLabel("Priority:"))
        self.combo_filter_priority = QComboBox()
        self.combo_filter_priority.addItem("All", "all")
        for p in ("P0", "P1", "P2", "P3"):
            self.combo_filter_priority.addItem(p, p)
        self.combo_filter_priority.addItem("(none)", "_none")
        self.combo_filter_priority.currentIndexChanged.connect(self._apply_filters)
        filter_bar.addWidget(self.combo_filter_priority)

        filter_bar.addWidget(QLabel("Auto Status:"))
        self.combo_filter_status = QComboBox()
        self.combo_filter_status.addItem("All", "all")
        for s in ("Ready", "Not Ready", "In Progress", "Blocked"):
            self.combo_filter_status.addItem(s, s)
        self.combo_filter_status.addItem("(none)", "_none")
        self.combo_filter_status.currentIndexChanged.connect(self._apply_filters)
        filter_bar.addWidget(self.combo_filter_status)

        filter_bar.addWidget(QLabel("Env:"))
        self.combo_filter_env = QComboBox()
        self.combo_filter_env.addItem("All", "all")
        for e in ("CI", "HIL"):
            self.combo_filter_env.addItem(e, e)
        self.combo_filter_env.addItem("(none)", "_none")
        self.combo_filter_env.currentIndexChanged.connect(self._apply_filters)
        filter_bar.addWidget(self.combo_filter_env)

        filter_bar.addStretch()

        self.lbl_count = QLabel()
        self.lbl_count.setStyleSheet("color: #a6adc8; font-size: 12px;")
        filter_bar.addWidget(self.lbl_count)

        root.addLayout(filter_bar)

        # ── Table ───────────────────────────────────────────────────────────
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels([h for h, _, _ in TABLE_COLUMNS])

        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.doubleClicked.connect(self._on_double_click)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(False)
        for col_idx, (_, _, width) in enumerate(TABLE_COLUMNS):
            self.table.setColumnWidth(col_idx, width)

        root.addWidget(self.table, 1)

        # ── Bottom action bar ───────────────────────────────────────────────
        action_bar = QHBoxLayout()

        btn_add = QPushButton("＋  Add Test Case")
        btn_add.clicked.connect(self._on_add)
        action_bar.addWidget(btn_add)

        btn_run = QPushButton("▶  Run")
        btn_run.setObjectName("success")
        btn_run.setToolTip(
            "Open the Run dialog. Pick one or more test cases, then execute "
            "automation and record the resulting PASS, FAIL or BLOCKED status."
        )
        btn_run.clicked.connect(self._on_run)
        action_bar.addWidget(btn_run)

        btn_timeline = QPushButton("📅  Timeline")
        btn_timeline.setObjectName("secondary")
        btn_timeline.setToolTip(
            "Open the view-only run timeline. Double-click a cell to "
            "view / edit / delete its run records."
        )
        btn_timeline.clicked.connect(self._on_timeline)
        action_bar.addWidget(btn_timeline)

        btn_refresh = QPushButton("↻  Refresh")
        btn_refresh.setObjectName("secondary")
        btn_refresh.clicked.connect(self._reload)
        action_bar.addWidget(btn_refresh)

        action_bar.addStretch()

        self.lbl_summary = QLabel()
        self.lbl_summary.setStyleSheet("color: #a6adc8; font-size: 12px;")
        action_bar.addWidget(self.lbl_summary)

        root.addLayout(action_bar)

        self._all_cases: list[dict] = []
        self._reload()

    # ── data ─────────────────────────────────────────────────────────────────

    def _current_version(self) -> str:
        return self.combo_version.currentData() or "automate_5"

    def _reload(self):
        ver = self._current_version()
        automate_dir = REPO_ROOT / ver
        self._all_cases = []
        files = discover_test_files(automate_dir)
        for sub, path in files.items():
            for tc in load_test_cases(path):
                tc["__subcomponent"] = sub
                self._all_cases.append(tc)
        self._apply_filters()

    def _apply_filters(self):
        sub_filter = self.combo_filter_sub.currentData()
        prio_filter = self.combo_filter_priority.currentData()
        status_filter = self.combo_filter_status.currentData()
        env_filter = self.combo_filter_env.currentData()

        def _match(tc: dict, value_key: str, filt: str) -> bool:
            if filt == "all":
                return True
            v = tc.get(value_key)
            if filt == "_none":
                return v in (None, "")
            return v == filt

        filtered = [
            c for c in self._all_cases
            if (sub_filter == "all" or c.get("__subcomponent") == sub_filter)
            and _match(c, "priority", prio_filter)
            and _match(c, "automation_status", status_filter)
            and _match(c, "test_environment_ci_hil", env_filter)
        ]

        self._populate_table(filtered)

    def _populate_table(self, cases: list[dict]):
        self.model.removeRows(0, self.model.rowCount())
        for tc in cases:
            self.model.appendRow(self._make_row(tc))
        self._update_counts(cases)

    @staticmethod
    def _format_cell_value(key: str, value) -> str:
        if value in (None, ""):
            return ""
        if key == "dependency" and isinstance(value, list):
            return ", ".join(value)
        if key == "steps" and isinstance(value, list):
            return " | ".join(f"{i}. {s}" for i, s in enumerate(value, 1))
        if isinstance(value, list):
            return "; ".join(str(v) for v in value)
        return str(value)

    def _make_row(self, tc: dict) -> list[QStandardItem]:
        items: list[QStandardItem] = []
        for header, key, _ in TABLE_COLUMNS:
            value = tc.get(key)
            text = self._format_cell_value(key, value)
            item = QStandardItem(text)
            full = text or "(empty)"
            item.setToolTip(full)
            if key == "test_case_id":
                item.setData(tc, Qt.ItemDataRole.UserRole)
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            elif key == "priority" and value in PRIORITY_COLOR:
                item.setForeground(PRIORITY_COLOR[value])
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            elif key == "automation_status" and value in AUTO_STATUS_COLOR:
                item.setForeground(AUTO_STATUS_COLOR[value])
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            elif key in ("severity", "test_environment_ci_hil"):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            items.append(item)
        return items

    def _update_counts(self, visible: list[dict]):
        total = len(self._all_cases)
        showing = len(visible)

        prio = {p: sum(1 for c in self._all_cases if c.get("priority") == p)
                for p in ("P0", "P1", "P2", "P3")}
        ready = sum(1 for c in self._all_cases if c.get("automation_status") == "Ready")
        not_ready = sum(1 for c in self._all_cases if c.get("automation_status") == "Not Ready")

        prio_str = "  ".join(f"{p}: {n}" for p, n in prio.items() if n)
        if prio_str:
            prio_str = "•  " + prio_str + "  "

        self.lbl_count.setText(f"Showing {showing} of {total}")
        self.lbl_summary.setText(
            f"{prio_str}•  Ready: {ready}   Not Ready: {not_ready}"
        )

    # ── selected test case ───────────────────────────────────────────────────

    def _selected_tc(self) -> dict | None:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        source_idx = self.proxy.mapToSource(idx)
        item = self.model.item(source_idx.row(), 0)  # test_case_id column
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # ── actions ──────────────────────────────────────────────────────────────

    def _on_double_click(self, _index):
        self._on_view()

    def _on_view(self):
        tc = self._selected_tc()
        if not tc:
            QMessageBox.information(self, "No Selection", "Select a test case first.")
            return
        dlg = DetailDialog(tc, self)
        result = dlg.exec()
        # If the user clicked Edit inside the detail view, open the editor.
        if result == DetailDialog.EDIT_REQUESTED:
            self._open_editor(tc)

    def _open_editor(self, tc: dict) -> None:
        sub = tc.get("__subcomponent")
        if not sub:
            QMessageBox.critical(
                self, "Error",
                "Cannot determine which subcomponent file owns this test case."
            )
            return
        dlg = TestCaseFormDialog(
            self._current_version(),
            existing_tc=tc,
            existing_subcomponent=sub,
            parent=self,
        )
        result = dlg.exec()
        if result in (QDialog.DialogCode.Accepted, TestCaseFormDialog.DELETED):
            self._reload()

    def _on_add(self):
        dlg = TestCaseFormDialog(self._current_version(), parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._reload()

    def _on_run(self):
        # Pre-tick the highlighted row (if any) inside the Run dialog as a
        # convenience; the user can change the selection there.
        sel = self._selected_tc()
        preselect = [sel.get("test_case_id")] if sel and sel.get("test_case_id") else []
        dlg = RunFormDialog(
            self._current_version(),
            test_case_ids=preselect,
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._reload()

    def _on_timeline(self):
        dlg = TimelineDialog(self._current_version(), parent=self)
        dlg.exec()


# ═══════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    app.setFont(QFont("Segoe UI", 10))

    win = MainWindow()
    win.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
