"""
Automate Validation – PyQt6 GUI

Launch:  python scripts/gui.py
"""

import sys
from datetime import date
from pathlib import Path

import yaml
from PyQt6.QtCore import Qt, QSortFilterProxyModel
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableView, QHeaderView, QPushButton, QComboBox, QLabel,
    QDialog, QFormLayout, QLineEdit, QTextEdit, QSpinBox,
    QDialogButtonBox, QMessageBox, QGroupBox, QSplitter,
    QTabWidget, QScrollArea, QFrame, QSizePolicy, QCheckBox,
    QAbstractItemView,
)

# ── Data layer (reuse from manage_tests.py) ──────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent

SUBCOMPONENTS = [
    "software",
    "mechanical",
    "holoscan_fpga",
    "multi_axis_motor_control_fpga",
]

PREFIX_MAP = {
    "software": "SW",
    "mechanical": "MECH",
    "holoscan_fpga": "HFPGA",
    "multi_axis_motor_control_fpga": "MAMC",
}

DISPLAY_NAMES = {
    "software": "Software",
    "mechanical": "Mechanical",
    "holoscan_fpga": "Holoscan FPGA",
    "multi_axis_motor_control_fpga": "Multi Axis Motor Control FPGA",
}


def discover_versions() -> list[str]:
    """Find all automate_* directories in the repo root."""
    return sorted(
        d.name for d in REPO_ROOT.iterdir()
        if d.is_dir() and d.name.startswith("automate_")
    )


def discover_test_files(automate_dir: Path) -> dict[str, Path]:
    found = {}
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
        yaml.dump({"test_cases": test_cases}, f,
                  default_flow_style=False, sort_keys=False, allow_unicode=True)


def next_test_id(existing_cases: list[dict], prefix: str) -> str:
    max_num = 0
    for tc in existing_cases:
        tid = tc.get("test_id", "")
        if tid.startswith(prefix + "-"):
            try:
                max_num = max(max_num, int(tid.split("-")[1]))
            except ValueError:
                pass
    return f"{prefix}-{max_num + 1:03d}"


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
QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 5px 10px;
    min-width: 160px;
    font-size: 13px;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #313244;
    color: #cdd6f4;
    selection-background-color: #585b70;
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
    background-color: #f38ba8;
}
QPushButton#danger:hover {
    background-color: #eba0ac;
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
QLineEdit, QTextEdit, QSpinBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 13px;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus {
    border: 1px solid #89b4fa;
}
QGroupBox {
    color: #89b4fa;
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
}
QTabWidget::pane {
    border: 1px solid #45475a;
    border-radius: 6px;
    background-color: #1e1e2e;
}
QTabBar::tab {
    background-color: #313244;
    color: #a6adc8;
    border: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 20px;
    margin-right: 2px;
    font-size: 13px;
}
QTabBar::tab:selected {
    background-color: #1e1e2e;
    color: #89b4fa;
    font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background-color: #45475a;
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
QCheckBox {
    color: #cdd6f4;
    font-size: 13px;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #45475a;
    border-radius: 4px;
    background-color: #313244;
}
QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}
QMessageBox {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
"""

# ── Colours for result badges ────────────────────────────────────────────────

COLOR_PASS   = QColor("#a6e3a1")
COLOR_FAIL   = QColor("#f38ba8")
COLOR_NONE   = QColor("#a6adc8")
COLOR_YES    = QColor("#89dceb")
COLOR_NO     = QColor("#6c7086")

TABLE_COLUMNS = [
    "Test ID", "Title", "Subcomponent", "Dependencies",
    "Steps", "Executed", "Result",
]


# ═══════════════════════════════════════════════════════════════════════════════
#  Detail Dialog – shows full test case info (read-only)
# ═══════════════════════════════════════════════════════════════════════════════

class DetailDialog(QDialog):
    def __init__(self, tc: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Test Case – {tc.get('test_id', '')}")
        self.setMinimumSize(620, 520)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header
        hdr = QLabel(f"{tc['test_id']}  —  {tc['title']}")
        hdr.setObjectName("heading")
        layout.addWidget(hdr)

        sub = QLabel(DISPLAY_NAMES.get(tc.get("subcomponent", ""), tc.get("subcomponent", "")))
        sub.setObjectName("subheading")
        layout.addWidget(sub)

        # Description
        grp_desc = QGroupBox("Description")
        gl = QVBoxLayout(grp_desc)
        desc = QLabel(tc.get("description", "").strip())
        desc.setWordWrap(True)
        gl.addWidget(desc)
        layout.addWidget(grp_desc)

        # Dependencies
        deps = ", ".join(tc.get("dependencies", [])) or "None"
        grp_dep = QGroupBox("Dependencies")
        dl = QVBoxLayout(grp_dep)
        dl.addWidget(QLabel(deps))
        layout.addWidget(grp_dep)

        # Test steps table
        grp_steps = QGroupBox(f"Test Steps ({len(tc.get('test_steps', []))})")
        sl = QVBoxLayout(grp_steps)
        steps_model = QStandardItemModel()
        steps_model.setHorizontalHeaderLabels(["#", "Action", "Expected Result"])
        for step in tc.get("test_steps", []):
            steps_model.appendRow([
                QStandardItem(str(step.get("step_number", ""))),
                QStandardItem(step.get("action", "")),
                QStandardItem(step.get("expected_result", "")),
            ])
        steps_table = QTableView()
        steps_table.setModel(steps_model)
        steps_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        steps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        steps_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        steps_table.verticalHeader().setVisible(False)
        steps_table.setAlternatingRowColors(True)
        steps_table.setMaximumHeight(180)
        sl.addWidget(steps_table)
        layout.addWidget(grp_steps)

        # Criteria
        crit = QGroupBox("Pass / Fail Criteria")
        cl = QFormLayout(crit)
        cl.addRow("Success:", self._wrap_label(tc.get("success_criteria", "")))
        cl.addRow("Failure:", self._wrap_label(tc.get("failure_criteria", "")))
        layout.addWidget(crit)

        # Execution status
        exec_grp = QGroupBox("Execution Status")
        el = QFormLayout(exec_grp)
        el.addRow("Executed:", QLabel("Yes" if tc.get("executed") else "No"))
        result_txt = (tc.get("result") or "—").upper()
        rl = QLabel(result_txt)
        if tc.get("result") == "pass":
            rl.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        elif tc.get("result") == "fail":
            rl.setStyleSheet("color: #f38ba8; font-weight: bold;")
        el.addRow("Result:", rl)
        el.addRow("Date:", QLabel(str(tc.get("execution_date") or "—")))
        el.addRow("By:", QLabel(str(tc.get("executed_by") or "—")))
        if tc.get("notes"):
            el.addRow("Notes:", self._wrap_label(tc.get("notes", "")))
        layout.addWidget(exec_grp)

        # Close button
        btn = QPushButton("Close")
        btn.setObjectName("secondary")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)

    @staticmethod
    def _wrap_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        return lbl


# ═══════════════════════════════════════════════════════════════════════════════
#  Add Test Case Dialog
# ═══════════════════════════════════════════════════════════════════════════════

class StepRow(QWidget):
    """One row representing a test step."""
    def __init__(self, num: int, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.num_label = QLabel(f"Step {num}")
        self.num_label.setFixedWidth(50)
        self.action = QLineEdit()
        self.action.setPlaceholderText("Action…")
        self.expected = QLineEdit()
        self.expected.setPlaceholderText("Expected result…")
        layout.addWidget(self.num_label)
        layout.addWidget(self.action, 2)
        layout.addWidget(self.expected, 2)

    def set_number(self, n: int):
        self.num_label.setText(f"Step {n}")

    def get_data(self) -> dict:
        return {
            "step_number": int(self.num_label.text().split()[1]),
            "action": self.action.text().strip(),
            "expected_result": self.expected.text().strip(),
        }


class AddTestDialog(QDialog):
    def __init__(self, version: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Test Case")
        self.setMinimumSize(680, 640)
        self.version = version
        self.step_rows: list[StepRow] = []

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        self.form_layout = QVBoxLayout(inner)
        self.form_layout.setSpacing(8)

        # -- Basic info --
        basic = QGroupBox("Basic Information")
        bl = QFormLayout(basic)

        self.combo_sub = QComboBox()
        for s in SUBCOMPONENTS:
            self.combo_sub.addItem(DISPLAY_NAMES[s], s)
        self.combo_sub.currentIndexChanged.connect(self._update_id_preview)
        bl.addRow("Subcomponent:", self.combo_sub)

        self.lbl_id = QLabel()
        self.lbl_id.setStyleSheet("color: #89b4fa; font-weight: bold;")
        bl.addRow("Test ID (auto):", self.lbl_id)

        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("Short descriptive title")
        bl.addRow("Title:", self.txt_title)

        self.txt_desc = QTextEdit()
        self.txt_desc.setPlaceholderText("Detailed description of what this test validates…")
        self.txt_desc.setMaximumHeight(80)
        bl.addRow("Description:", self.txt_desc)

        self.txt_deps = QLineEdit()
        self.txt_deps.setPlaceholderText("Comma-separated test IDs, e.g. SW-001, MECH-002")
        bl.addRow("Dependencies:", self.txt_deps)

        self.form_layout.addWidget(basic)

        # -- Test steps --
        steps_grp = QGroupBox("Test Steps")
        self.steps_layout = QVBoxLayout(steps_grp)

        btn_row = QHBoxLayout()
        btn_add_step = QPushButton("+ Add Step")
        btn_add_step.setObjectName("secondary")
        btn_add_step.clicked.connect(self._add_step)
        btn_rm_step = QPushButton("− Remove Last")
        btn_rm_step.setObjectName("danger")
        btn_rm_step.clicked.connect(self._remove_step)
        btn_row.addWidget(btn_add_step)
        btn_row.addWidget(btn_rm_step)
        btn_row.addStretch()
        self.steps_layout.addLayout(btn_row)

        self.steps_container = QVBoxLayout()
        self.steps_layout.addLayout(self.steps_container)
        self.form_layout.addWidget(steps_grp)

        # Start with one step
        self._add_step()

        # -- Criteria --
        crit = QGroupBox("Pass / Fail Criteria")
        cl = QFormLayout(crit)
        self.txt_success = QLineEdit()
        self.txt_success.setPlaceholderText("What constitutes a passing test")
        cl.addRow("Success criteria:", self.txt_success)
        self.txt_failure = QLineEdit()
        self.txt_failure.setPlaceholderText("What constitutes a failing test")
        cl.addRow("Failure criteria:", self.txt_failure)
        self.form_layout.addWidget(crit)

        self.form_layout.addStretch()
        scroll.setWidget(inner)

        # -- Button box --
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self._on_save)
        bbox.rejected.connect(self.reject)
        for btn in bbox.buttons():
            if bbox.buttonRole(btn) == QDialogButtonBox.ButtonRole.AcceptRole:
                btn.setObjectName("success")

        outer = QVBoxLayout(self)
        outer.addWidget(scroll)
        outer.addWidget(bbox)

        self._update_id_preview()

    # -- helpers --

    def _update_id_preview(self):
        sub = self.combo_sub.currentData()
        prefix = PREFIX_MAP[sub]
        cases = self._load_sub_cases(sub)
        self.lbl_id.setText(next_test_id(cases, prefix))

    def _load_sub_cases(self, sub: str) -> list[dict]:
        p = REPO_ROOT / self.version / sub / "test_cases.yaml"
        return load_test_cases(p) if p.exists() else []

    def _add_step(self):
        row = StepRow(len(self.step_rows) + 1)
        self.step_rows.append(row)
        self.steps_container.addWidget(row)

    def _remove_step(self):
        if self.step_rows:
            row = self.step_rows.pop()
            self.steps_container.removeWidget(row)
            row.deleteLater()

    def _on_save(self):
        sub = self.combo_sub.currentData()
        title = self.txt_title.text().strip()
        desc = self.txt_desc.toPlainText().strip()
        success = self.txt_success.text().strip()
        failure = self.txt_failure.text().strip()

        if not title:
            QMessageBox.warning(self, "Validation", "Title is required.")
            return
        if not desc:
            QMessageBox.warning(self, "Validation", "Description is required.")
            return
        if not self.step_rows:
            QMessageBox.warning(self, "Validation", "At least one test step is required.")
            return
        for i, sr in enumerate(self.step_rows, 1):
            d = sr.get_data()
            if not d["action"] or not d["expected_result"]:
                QMessageBox.warning(self, "Validation", f"Step {i} is incomplete.")
                return
        if not success:
            QMessageBox.warning(self, "Validation", "Success criteria is required.")
            return
        if not failure:
            QMessageBox.warning(self, "Validation", "Failure criteria is required.")
            return

        # Build dependencies list
        deps_text = self.txt_deps.text().strip()
        deps = [d.strip() for d in deps_text.split(",") if d.strip()] if deps_text else []

        # Build test case
        yaml_path = REPO_ROOT / self.version / sub / "test_cases.yaml"
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        cases = load_test_cases(yaml_path) if yaml_path.exists() else []
        tid = next_test_id(cases, PREFIX_MAP[sub])

        tc = {
            "test_id": tid,
            "title": title,
            "subcomponent": sub,
            "description": desc + "\n",
            "dependencies": deps,
            "test_steps": [sr.get_data() for sr in self.step_rows],
            "success_criteria": success,
            "failure_criteria": failure,
            "executed": False,
            "result": None,
            "execution_date": None,
            "executed_by": None,
            "notes": "",
        }
        cases.append(tc)
        save_test_cases(yaml_path, cases)
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════════
#  Record Result Dialog
# ═══════════════════════════════════════════════════════════════════════════════

class RecordResultDialog(QDialog):
    def __init__(self, tc: dict, version: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Record Result – {tc['test_id']}")
        self.setMinimumWidth(420)
        self.tc = tc
        self.version = version

        layout = QFormLayout(self)
        layout.setSpacing(10)

        hdr = QLabel(f"{tc['test_id']}  —  {tc['title']}")
        hdr.setObjectName("heading")
        hdr.setStyleSheet("font-size: 16px;")
        layout.addRow(hdr)

        self.combo_result = QComboBox()
        self.combo_result.addItem("Pass", "pass")
        self.combo_result.addItem("Fail", "fail")
        layout.addRow("Result:", self.combo_result)

        self.txt_by = QLineEdit()
        self.txt_by.setPlaceholderText("Your name")
        layout.addRow("Executed by:", self.txt_by)

        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText("Optional notes…")
        self.txt_notes.setMaximumHeight(80)
        layout.addRow("Notes:", self.txt_notes)

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self._on_save)
        bbox.rejected.connect(self.reject)
        layout.addRow(bbox)

    def _on_save(self):
        by = self.txt_by.text().strip()
        if not by:
            QMessageBox.warning(self, "Validation", "Executed by is required.")
            return

        result = self.combo_result.currentData()
        notes = self.txt_notes.toPlainText().strip()
        sub = self.tc["subcomponent"]
        yaml_path = REPO_ROOT / self.version / sub / "test_cases.yaml"
        cases = load_test_cases(yaml_path)
        for c in cases:
            if c["test_id"] == self.tc["test_id"]:
                c["executed"] = True
                c["result"] = result
                c["execution_date"] = str(date.today())
                c["executed_by"] = by
                c["notes"] = notes
                break
        save_test_cases(yaml_path, cases)
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════════
#  Main Window
# ═══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Automate Stack Validation")
        self.setMinimumSize(1100, 640)
        self.resize(1280, 720)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # ── Top bar ──────────────────────────────────────────────────────────
        top_bar = QHBoxLayout()

        title_block = QVBoxLayout()
        title = QLabel("Automate Stack Validation")
        title.setObjectName("heading")
        title_block.addWidget(title)
        subtitle = QLabel("Test case database  •  View, add, and record results")
        subtitle.setObjectName("subheading")
        title_block.addWidget(subtitle)
        top_bar.addLayout(title_block)
        top_bar.addStretch()

        # Version selector
        top_bar.addWidget(QLabel("Version:"))
        self.combo_version = QComboBox()
        for v in discover_versions():
            self.combo_version.addItem(v.replace("_", " ").title(), v)
        self.combo_version.currentIndexChanged.connect(self._reload)
        top_bar.addWidget(self.combo_version)

        root.addLayout(top_bar)

        # ── Filter bar ───────────────────────────────────────────────────────
        filter_bar = QHBoxLayout()

        filter_bar.addWidget(QLabel("Subcomponent:"))
        self.combo_filter_sub = QComboBox()
        self.combo_filter_sub.addItem("All", "all")
        for s in SUBCOMPONENTS:
            self.combo_filter_sub.addItem(DISPLAY_NAMES[s], s)
        self.combo_filter_sub.currentIndexChanged.connect(self._apply_filters)
        filter_bar.addWidget(self.combo_filter_sub)

        filter_bar.addWidget(QLabel("Status:"))
        self.combo_filter_exec = QComboBox()
        self.combo_filter_exec.addItem("All", "all")
        self.combo_filter_exec.addItem("Not Executed", "no")
        self.combo_filter_exec.addItem("Executed", "yes")
        self.combo_filter_exec.currentIndexChanged.connect(self._apply_filters)
        filter_bar.addWidget(self.combo_filter_exec)

        filter_bar.addWidget(QLabel("Result:"))
        self.combo_filter_result = QComboBox()
        self.combo_filter_result.addItem("All", "all")
        self.combo_filter_result.addItem("Pass", "pass")
        self.combo_filter_result.addItem("Fail", "fail")
        self.combo_filter_result.addItem("Pending", "pending")
        self.combo_filter_result.currentIndexChanged.connect(self._apply_filters)
        filter_bar.addWidget(self.combo_filter_result)

        filter_bar.addStretch()

        self.lbl_count = QLabel()
        self.lbl_count.setStyleSheet("color: #a6adc8; font-size: 12px;")
        filter_bar.addWidget(self.lbl_count)

        root.addLayout(filter_bar)

        # ── Table ────────────────────────────────────────────────────────────
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(TABLE_COLUMNS)

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
        self.table.doubleClicked.connect(self._on_double_click)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Title stretches
        hh.setStretchLastSection(True)

        root.addWidget(self.table, 1)

        # ── Bottom action bar ────────────────────────────────────────────────
        action_bar = QHBoxLayout()

        btn_add = QPushButton("＋  Add Test Case")
        btn_add.clicked.connect(self._on_add)
        action_bar.addWidget(btn_add)

        btn_view = QPushButton("View Details")
        btn_view.setObjectName("secondary")
        btn_view.clicked.connect(self._on_view)
        action_bar.addWidget(btn_view)

        btn_record = QPushButton("Record Result")
        btn_record.setObjectName("success")
        btn_record.clicked.connect(self._on_record)
        action_bar.addWidget(btn_record)

        btn_refresh = QPushButton("↻  Refresh")
        btn_refresh.setObjectName("secondary")
        btn_refresh.clicked.connect(self._reload)
        action_bar.addWidget(btn_refresh)

        action_bar.addStretch()

        # Summary chips
        self.lbl_summary = QLabel()
        self.lbl_summary.setStyleSheet("color: #a6adc8; font-size: 12px;")
        action_bar.addWidget(self.lbl_summary)

        root.addLayout(action_bar)

        # ── Load data ────────────────────────────────────────────────────────
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
            self._all_cases.extend(load_test_cases(path))
        self._apply_filters()

    def _apply_filters(self):
        sub_filter = self.combo_filter_sub.currentData()
        exec_filter = self.combo_filter_exec.currentData()
        result_filter = self.combo_filter_result.currentData()

        filtered = self._all_cases
        if sub_filter != "all":
            filtered = [c for c in filtered if c.get("subcomponent") == sub_filter]
        if exec_filter == "yes":
            filtered = [c for c in filtered if c.get("executed")]
        elif exec_filter == "no":
            filtered = [c for c in filtered if not c.get("executed")]
        if result_filter == "pass":
            filtered = [c for c in filtered if c.get("result") == "pass"]
        elif result_filter == "fail":
            filtered = [c for c in filtered if c.get("result") == "fail"]
        elif result_filter == "pending":
            filtered = [c for c in filtered if not c.get("result")]

        self._populate_table(filtered)

    def _populate_table(self, cases: list[dict]):
        self.model.removeRows(0, self.model.rowCount())
        for tc in cases:
            row = self._make_row(tc)
            self.model.appendRow(row)
        self._update_counts(cases)

    def _make_row(self, tc: dict) -> list[QStandardItem]:
        tid = QStandardItem(tc.get("test_id", ""))
        tid.setData(tc, Qt.ItemDataRole.UserRole)  # store full dict

        title = QStandardItem(tc.get("title", ""))
        sub = QStandardItem(DISPLAY_NAMES.get(tc.get("subcomponent", ""), tc.get("subcomponent", "")))
        deps = QStandardItem(", ".join(tc.get("dependencies", [])) or "None")
        steps = QStandardItem(str(len(tc.get("test_steps", []))))
        steps.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        executed = QStandardItem("Yes" if tc.get("executed") else "No")
        executed.setForeground(COLOR_YES if tc.get("executed") else COLOR_NO)
        executed.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        result_val = tc.get("result")
        result = QStandardItem((result_val or "—").upper())
        if result_val == "pass":
            result.setForeground(COLOR_PASS)
        elif result_val == "fail":
            result.setForeground(COLOR_FAIL)
        else:
            result.setForeground(COLOR_NONE)
        result.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        font = result.font()
        font.setBold(True)
        result.setFont(font)

        return [tid, title, sub, deps, steps, executed, result]

    def _update_counts(self, visible: list[dict]):
        total = len(self._all_cases)
        showing = len(visible)
        passed = sum(1 for c in self._all_cases if c.get("result") == "pass")
        failed = sum(1 for c in self._all_cases if c.get("result") == "fail")
        pending = total - passed - failed
        self.lbl_count.setText(f"Showing {showing} of {total}")
        self.lbl_summary.setText(
            f"✓ {passed} passed   ✗ {failed} failed   ○ {pending} pending"
        )

    # ── selected test case ───────────────────────────────────────────────────

    def _selected_tc(self) -> dict | None:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        source_idx = self.proxy.mapToSource(idx)
        row = source_idx.row()
        item = self.model.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # ── actions ──────────────────────────────────────────────────────────────

    def _on_double_click(self, index):
        self._on_view()

    def _on_view(self):
        tc = self._selected_tc()
        if not tc:
            QMessageBox.information(self, "No Selection", "Select a test case first.")
            return
        DetailDialog(tc, self).exec()

    def _on_add(self):
        dlg = AddTestDialog(self._current_version(), self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._reload()

    def _on_record(self):
        tc = self._selected_tc()
        if not tc:
            QMessageBox.information(self, "No Selection", "Select a test case first.")
            return
        dlg = RecordResultDialog(tc, self._current_version(), self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._reload()


# ═══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)

    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
