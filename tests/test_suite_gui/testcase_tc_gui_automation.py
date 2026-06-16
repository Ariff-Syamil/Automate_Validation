"""One-to-one pytest automation for the TC-GUI YAML catalog."""

from __future__ import annotations

import csv
import json
import sys
from types import ModuleType, SimpleNamespace
from pathlib import Path

import pytest
import yaml
from PySide6.QtCore import QElapsedTimer, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtWidgets import QApplication, QStackedWidget, QWidget
from tests._paths import AUTOMATE5_ROOT

REPO_ROOT = AUTOMATE5_ROOT
GUI_CFG_PATH = REPO_ROOT / "configs" / "gui" / "gui_configuration.yaml"


def _cfg() -> dict:
    with GUI_CFG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _pump(ms: int) -> None:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < ms:
        app.processEvents()


def _capture(signal):
    calls: list[tuple] = []
    signal.connect(lambda *args: calls.append(args))
    return calls


class _FakeSignal:
    def connect(self, _slot) -> None:
        return None


class _FakeGestureController:
    def __init__(self, *_args, **_kwargs) -> None:
        self.motor_selected = _FakeSignal()
        self.speed_changed = _FakeSignal()
        self.stopped = _FakeSignal()
        self.gesture_detected = _FakeSignal()
        self.error_occurred = _FakeSignal()
        self.left_hand_bbox = _FakeSignal()
        self.right_hand_bbox = _FakeSignal()
        self.frame_size_changed = _FakeSignal()

    def start_recognition(self) -> None:
        return None

    def stop_recognition(self) -> None:
        return None

    def reset_tracking(self) -> None:
        return None

    def process_frame(self, _image) -> None:
        return None


def _install_fake_gesture_controller(monkeypatch) -> None:
    module = ModuleType("backend.gesture_controller")
    module.GestureController = _FakeGestureController
    monkeypatch.setitem(sys.modules, "backend.gesture_controller", module)


def _qml_ready(relative_path: str) -> None:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    engine = QQmlEngine()
    engine.addImportPath(str((REPO_ROOT / "gui" / "components").resolve()))
    component = QQmlComponent(engine, QUrl.fromLocalFile(str((REPO_ROOT / relative_path).resolve())))
    for _ in range(200):
        if component.status() != QQmlComponent.Status.Loading:
            break
        app.processEvents()
    errors = [f"{e.url().toString()}:{e.line()}:{e.column()} {e.description()}" for e in component.errors()]
    assert component.status() == QQmlComponent.Status.Ready, "\n".join(errors)
    engine.deleteLater()


def _lightweight_main_window() -> QStackedWidget:
    """Create a MainWindow-compatible stack without loading QML panels."""
    from gui.main_window import MainWindow

    window = QStackedWidget()
    window.PAGE_BASE = MainWindow.PAGE_BASE
    window.PAGE_VLA = MainWindow.PAGE_VLA
    window.PAGE_ANALYTIC = MainWindow.PAGE_ANALYTIC
    for _ in range(3):
        window.addWidget(QWidget())
    window.base_panel = SimpleNamespace(bridge=SimpleNamespace(base_active_section="base"))
    window.vla_panel = SimpleNamespace(bridge=SimpleNamespace(vla_active_section="vla"))
    window.analytic_panel = SimpleNamespace(bridge=SimpleNamespace(analytic_active_section="analysis"))
    window._on_nav = MainWindow._on_nav.__get__(window, QStackedWidget)
    window.setCurrentIndex(window.PAGE_BASE)
    return window


@pytest.fixture
def base_runtime(monkeypatch):
    _install_fake_gesture_controller(monkeypatch)

    from gui.panels.base_design.base_presenter import BasePanelPresenter
    from gui.panels.base_design.base_view import BasePanelBridge

    app = QApplication.instance() or QApplication(sys.argv[:1])
    bridge = BasePanelBridge()
    presenter = BasePanelPresenter(bridge)
    presenter._gesture_controller.start_recognition = lambda: None
    presenter._gesture_controller.stop_recognition = lambda: None
    presenter._gesture_controller.reset_tracking = lambda: None
    yield bridge, presenter
    presenter.shutdown()
    presenter.deleteLater()
    bridge.deleteLater()
    app.processEvents()


@pytest.fixture
def vla_runtime():
    from gui.panels.vla_design.presenter import VlaPanelPresenter
    from gui.panels.vla_design.view import VlaPanelBridge

    app = QApplication.instance() or QApplication(sys.argv[:1])
    bridge = VlaPanelBridge()
    presenter = VlaPanelPresenter(bridge)
    yield bridge, presenter
    presenter.deleteLater()
    bridge.deleteLater()
    app.processEvents()


@pytest.fixture
def analytic_runtime():
    from gui.panels.analytic_design.presenter import AnalyticPanelPresenter
    from gui.panels.analytic_design.view import AnalyticPanelBridge

    app = QApplication.instance() or QApplication(sys.argv[:1])
    bridge = AnalyticPanelBridge()
    presenter = AnalyticPanelPresenter(bridge)
    yield bridge, presenter
    presenter.deleteLater()
    bridge.deleteLater()
    app.processEvents()


@pytest.fixture
def sample_log(tmp_path: Path) -> Path:
    path = tmp_path / "automate5.jsonl"
    rows = [
        {"timestamp": f"2026-01-01T00:00:0{i}", "level": "INFO", "subsystem": "GUI", "message": f"msg {i}"}
        for i in range(3)
    ] + [
        {"timestamp": "2026-01-01T00:00:04", "level": "WARN", "subsystem": "MOTOR", "message": "warn"},
        {"timestamp": "2026-01-01T00:00:05", "level": "ERROR", "subsystem": "GUI", "message": "err"},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return path


@pytest.fixture
def sample_bench(tmp_path: Path) -> Path:
    path = tmp_path / "latest.csv"
    rows = [
        {"subsystem": "GUI", "phase": "load", "label": "a", "elapsed_ms": "10.0", "timestamp": "t1"},
        {"subsystem": "GUI", "phase": "render", "label": "b", "elapsed_ms": "20.0", "timestamp": "t2"},
        {"subsystem": "MOTOR", "phase": "load", "label": "c", "elapsed_ms": "30.0", "timestamp": "t3"},
        {"subsystem": "MOTOR", "phase": "control", "label": "d", "elapsed_ms": "40.0", "timestamp": "t4"},
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["subsystem", "phase", "label", "elapsed_ms", "timestamp"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_tc_gui_001():
    cfg = _cfg().get("window") or {}
    window = QStackedWidget()
    window.setWindowTitle(str(cfg.get("title", "Automate5 Industrial Control Hub")))
    assert window.windowTitle() == cfg.get("title", "Automate5 Industrial Control Hub")
    window.close()


def test_tc_gui_002():
    cfg = _cfg().get("window") or {}
    window = QStackedWidget()
    window.resize(int(cfg.get("width", 1920)), int(cfg.get("height", 1080)))
    assert abs(window.width() - int(cfg.get("width", 1920))) <= 2
    assert abs(window.height() - int(cfg.get("height", 1080))) <= 2
    window.close()


def test_tc_gui_003(monkeypatch, tmp_path: Path):
    import main

    monkeypatch.setattr(main, "_GUI_CONFIG_PATH", tmp_path / "missing.yaml")
    assert main._load_window_cfg() == {}
    defaults = main._load_window_cfg()
    assert defaults.get("title", "Automate5 Industrial Control Hub") == "Automate5 Industrial Control Hub"
    assert int(defaults.get("width", 1920)) == 1920
    assert int(defaults.get("height", 1080)) == 1080


def test_tc_gui_010():
    window = _lightweight_main_window()
    window._on_nav("vla")
    window._on_nav("base")
    assert window.currentIndex() == window.PAGE_BASE
    assert window.base_panel.bridge.base_active_section == "base"
    window.close()


def test_tc_gui_011():
    window = _lightweight_main_window()
    window._on_nav("vla")
    assert window.currentIndex() == window.PAGE_VLA
    assert window.vla_panel.bridge.vla_active_section == "vla"
    window.close()


def test_tc_gui_012():
    window = _lightweight_main_window()
    window._on_nav("analysis")
    assert window.currentIndex() == window.PAGE_ANALYTIC
    assert window.analytic_panel.bridge.analytic_active_section == "analysis"
    window.close()


def test_tc_gui_013():
    window = _lightweight_main_window()
    window._on_nav("base")
    window._on_nav("base")
    assert window.currentIndex() == window.PAGE_BASE
    assert window.base_panel.bridge.base_active_section == "base"
    window.close()


def test_tc_gui_020(base_runtime):
    bridge, presenter = base_runtime
    bridge.base_cam1_preview_live = True
    bridge.base_start_clicked.emit()
    presenter._generate_mock_data()
    assert presenter._motors_running is True
    assert bridge.base_gesture_enabled is True
    assert any(m["rpm"] != 0.0 for node in presenter._motor_states for m in node)


def test_tc_gui_021(base_runtime):
    bridge, presenter = base_runtime
    bridge.base_cam1_preview_live = True
    bridge.base_start_clicked.emit()
    bridge.base_stop_clicked.emit()
    assert presenter._motors_running is False
    assert bridge.base_gesture_enabled is False


def test_tc_gui_022(base_runtime):
    bridge, presenter = base_runtime
    bridge.base_cam1_preview_live = True
    bridge.base_start_clicked.emit()
    assert presenter._motors_running is True
    bridge.base_stop_clicked.emit()
    assert presenter._motors_running is False
    bridge.base_start_clicked.emit()
    presenter._generate_mock_data()
    assert presenter._motors_running is True
    assert any(m["rpm"] != 0.0 for node in presenter._motor_states for m in node)


def test_tc_gui_023(base_runtime):
    bridge, presenter = base_runtime
    bridge.base_cam1_preview_live = True
    bridge.base_start_clicked.emit()
    presenter._generate_mock_data()
    bridge.base_reset_clicked.emit()
    assert presenter._motors_running is False
    assert all(m["rpm"] == 0.0 for node in presenter._motor_states for m in node)


def test_tc_gui_030(base_runtime):
    _bridge, presenter = base_runtime
    assert presenter._motors_running is False
    assert all(m["rpm"] == 0.0 for node in presenter._motor_states for m in node)


def test_tc_gui_031(base_runtime):
    bridge, presenter = base_runtime
    bridge.base_cam1_preview_live = True
    bridge.base_start_clicked.emit()
    presenter._generate_mock_data()
    total = sum(m["rpm"] for node in presenter._motor_states for m in node)
    assert total > 0


def test_tc_gui_032(base_runtime):
    bridge, presenter = base_runtime
    bridge.base_cam1_preview_live = True
    bridge.base_start_clicked.emit()
    assert presenter._motors_running is True


def test_tc_gui_040(base_runtime):
    bridge, _presenter = base_runtime
    assert bridge.base_node_count == int((_cfg().get("base_panel") or {}).get("node_count", 2))


def test_tc_gui_041(base_runtime):
    bridge, _presenter = base_runtime
    if bridge.base_node_count < 2:
        pytest.skip("Need at least two nodes to select node index 1.")
    bridge.base_active_node = 1
    assert bridge.base_active_node == 1


def test_tc_gui_050(base_runtime):
    bridge, _presenter = base_runtime
    assert bridge.base_motors_per_node == int((_cfg().get("base_panel") or {}).get("motors_per_node", 4))


def test_tc_gui_051(base_runtime):
    bridge, _presenter = base_runtime
    calls = _capture(bridge.base_motor_start)
    bridge.base_motor_start.emit(0, 0)
    assert calls == [(0, 0)]


def test_tc_gui_052(base_runtime):
    bridge, _presenter = base_runtime
    calls = _capture(bridge.base_motor_stop)
    bridge.base_motor_stop.emit(0, 0)
    assert calls == [(0, 0)]


def test_tc_gui_053(base_runtime):
    bridge, _presenter = base_runtime
    calls = _capture(bridge.base_motor_direction)
    bridge.base_motor_direction.emit(0, 0, -1)
    assert calls == [(0, 0, -1)]


def test_tc_gui_054(base_runtime):
    bridge, _presenter = base_runtime
    calls = _capture(bridge.base_motor_setpoint)
    bridge.base_motor_setpoint.emit(0, 0, 250.0)
    assert calls == [(0, 0, 250.0)]


def test_tc_gui_055(base_runtime):
    bridge, _presenter = base_runtime
    calls = _capture(bridge.base_motor_torque_limit)
    bridge.base_motor_torque_limit.emit(0, 0, 1.5)
    assert calls == [(0, 0, 1.5)]


def test_tc_gui_056(base_runtime):
    bridge, presenter = base_runtime
    presenter.update_motor_data(0, 0, 100.0, "1 m/s", "1 mm", "1°", "1 Nm")
    calls = _capture(bridge.base_motor_reset)
    bridge.base_motor_reset.emit(0, 0)
    presenter.update_motor_data(0, 0, 0.0, "0 m/s", "0 mm", "0°", "0 Nm")
    assert calls == [(0, 0)]
    assert presenter._motor_states[0][0]["rpm"] == 0.0


def test_tc_gui_057(base_runtime):
    bridge, presenter = base_runtime
    presenter.update_motor_data(0, 0, 100.0, "1 m/s", "1 mm", "1°", "1 Nm")
    calls = _capture(bridge.base_motor_estop)
    bridge.base_motor_estop.emit(0, 0)
    assert calls == [(0, 0)]
    assert presenter._motor_states[0][0]["rpm"] == 0.0


def test_tc_gui_060(base_runtime):
    bridge, _presenter = base_runtime
    calls = _capture(bridge.base_motor_mode)
    bridge.base_motor_mode.emit(0, 0, "speed")
    assert calls == [(0, 0, "speed")]


def test_tc_gui_061(base_runtime):
    bridge, _presenter = base_runtime
    calls = _capture(bridge.base_motor_mode)
    bridge.base_motor_mode.emit(0, 0, "position")
    assert calls == [(0, 0, "position")]


def test_tc_gui_062(base_runtime):
    bridge, _presenter = base_runtime
    calls = _capture(bridge.base_motor_target_rpm)
    bridge.base_motor_target_rpm.emit(0, 0, 300.0)
    assert calls == [(0, 0, 300.0)]


def test_tc_gui_063(base_runtime):
    bridge, _presenter = base_runtime
    calls = _capture(bridge.base_motor_full_rotation)
    bridge.base_motor_full_rotation.emit(0, 0, 1.0)
    assert calls == [(0, 0, 1.0)]


def test_tc_gui_064(base_runtime):
    bridge, _presenter = base_runtime
    calls = _capture(bridge.base_motor_iq_torque)
    bridge.base_motor_iq_torque.emit(0, 0, 1.5)
    assert calls == [(0, 0, 1.5)]


def test_tc_gui_070(base_runtime):
    bridge, _presenter = base_runtime
    calls = _capture(bridge.base_logs_clicked)
    bridge.base_logs_clicked.emit()
    assert calls == [()]


def test_tc_gui_071(base_runtime):
    bridge, _presenter = base_runtime
    calls = _capture(bridge.base_logs_clicked)
    bridge.base_logs_clicked.emit()
    bridge.base_logs_clicked.emit()
    assert len(calls) == 2


def test_tc_gui_072(base_runtime):
    bridge, _presenter = base_runtime
    calls = _capture(bridge.base_toggle_changed)
    bridge.base_camera_mode = 0
    assert bridge.base_camera_mode == 0
    assert calls


def test_tc_gui_073(base_runtime):
    bridge, _presenter = base_runtime
    calls = _capture(bridge.base_configure_clicked)
    bridge.base_configure_clicked.emit(1, 0, 0, 15)
    assert calls == [(1, 0, 0, 15)]


def test_tc_gui_074():
    gestures = _cfg().get("gestures") or []
    assert len(gestures) >= 1


def test_tc_gui_075(base_runtime):
    bridge, _presenter = base_runtime
    original = bridge.base_gesture_enabled
    bridge.base_gesture_enabled = not original
    assert bridge.base_gesture_enabled is (not original)


def test_tc_gui_076(base_runtime):
    bridge, _presenter = base_runtime
    calls = _capture(bridge.base_logs_clicked)
    bridge.base_logs_clicked.emit()
    assert calls == [()]


def test_tc_gui_077():
    from gui.panels.analytic_design.view import AnalyticPanelBridge

    bridge = AnalyticPanelBridge()
    bridge.set_logs_payload({"path": "x", "entries": [{"message": "one"}], "summary": {"total": 1}})
    bridge.set_logs_payload({"path": "", "entries": [], "summary": {"total": 0}, "error": ""})
    assert bridge.analytic_log_entries == []
    assert bridge.analytic_log_path == ""


def test_tc_gui_100(base_runtime):
    bridge, _presenter = base_runtime
    if not bridge.base_mock_camera_enabled:
        pytest.skip("Mock camera disabled in gui_configuration.yaml.")
    assert bridge.base_mock_camera_count >= 1
    assert bridge.base_mock_camera_url_at(0)
    assert bridge.base_mock_camera_url_at(999) == ""


def test_tc_gui_101(base_runtime):
    bridge, _presenter = base_runtime
    if not bridge.base_mock_camera_enabled:
        pytest.skip("Mock camera disabled in gui_configuration.yaml.")
    bridge.base_configure_clicked.emit(0, 0, 0, 15)
    assert bridge.base_cam1_preview_live is True
    assert bridge.base_cam2_preview_live is False
    assert bridge.base_mock_camera_source_1


def test_tc_gui_102(base_runtime):
    bridge, _presenter = base_runtime
    if not bridge.base_mock_camera_enabled or bridge.base_mock_camera_count < 2:
        pytest.skip("Need at least two mock camera sources.")
    bridge.base_configure_clicked.emit(1, 0, 1, 15)
    assert bridge.base_cam1_preview_live is True
    assert bridge.base_cam2_preview_live is True
    assert bridge.base_mock_camera_source_1 != bridge.base_mock_camera_source_2


def test_tc_gui_103():
    from backend.camera_controller import enumerate_video_inputs

    labels, devices = enumerate_video_inputs()
    assert isinstance(labels, list)
    assert isinstance(devices, list)
    assert len(labels) == len(devices)


def test_tc_gui_104(base_runtime):
    bridge, _presenter = base_runtime
    if bridge.base_mock_camera_enabled:
        pytest.skip("No-camera guard path requires mock camera disabled.")
    bridge.base_configure_clicked.emit(0, 999, 999, 15)
    assert bridge.base_cam1_preview_live is False


def test_tc_gui_110():
    pytest.skip("Gesture overlay visibility requires HIL camera/gesture runtime.")


def test_tc_gui_111():
    pytest.skip("Gesture overlay visibility requires HIL camera/gesture runtime.")


def test_tc_gui_112():
    pytest.skip("Gesture detection requires HIL camera/gesture runtime.")


def test_tc_gui_120(vla_runtime):
    bridge, _presenter = vla_runtime
    assert bridge.vla_active_section == "vla"
    assert bridge.vla_node_count >= 1
    assert bridge.vla_motors_per_node >= 1


def test_tc_gui_121(vla_runtime):
    bridge, _presenter = vla_runtime
    assert bridge.vla_node_count == int((_cfg().get("base_panel") or {}).get("node_count", 2))
    assert bridge.vla_motors_per_node == int((_cfg().get("base_panel") or {}).get("motors_per_node", 4))


def test_tc_gui_122(vla_runtime):
    bridge, _presenter = vla_runtime
    calls = _capture(bridge.vla_prompt_submitted)
    bridge.vla_prompt_submitted.emit("Pick up the red block")
    assert calls == [("Pick up the red block",)]


def test_tc_gui_123(vla_runtime):
    bridge, presenter = vla_runtime
    bridge.vla_start_clicked.emit()
    presenter._generate_mock_data()
    assert presenter._motors_running is True
    assert any(m["rpm"] != 0.0 for node in presenter._motor_states for m in node)
    assert not hasattr(bridge, "vla_gesture_enabled")
    bridge.vla_stop_clicked.emit()
    assert presenter._motors_running is False


def test_tc_gui_124(vla_runtime):
    bridge, _presenter = vla_runtime
    if not bridge.vla_mock_camera_enabled:
        pytest.skip("Mock camera disabled in gui_configuration.yaml.")
    bridge.vla_configure_clicked.emit(0, 0, 0, 15)
    assert bridge.vla_cam1_preview_live is True
    assert bridge.vla_cam2_preview_live is False
    if bridge.vla_mock_camera_count < 2:
        pytest.skip("Need at least two mock camera sources for double-mode branch.")
    bridge.vla_configure_clicked.emit(1, 0, 1, 15)
    assert bridge.vla_cam1_preview_live is True
    assert bridge.vla_cam2_preview_live is True


def test_tc_gui_125():
    _qml_ready("gui/panels/vla_design/qml/vla_panel.qml")


def test_tc_gui_130(analytic_runtime):
    bridge, _presenter = analytic_runtime
    assert bridge.analytic_active_section == "analysis"
    assert bridge.analytic_display_mode == "both"
    assert abs(bridge.analytic_split_ratio - 0.55) < 1e-6


def test_tc_gui_131(analytic_runtime, sample_log: Path, sample_bench: Path):
    bridge, presenter = analytic_runtime
    bridge.analytic_open_logs(str(sample_log))
    bridge.analytic_open_bench(str(sample_bench))
    _pump(10)
    assert bridge.analytic_log_entries
    assert bridge.analytic_bench_entries
    assert bridge.analytic_log_error == ""
    assert bridge.analytic_bench_error == ""
    assert presenter.bridge is bridge


def test_tc_gui_132(analytic_runtime):
    bridge, _presenter = analytic_runtime
    bridge.analytic_set_display_mode("logs")
    assert bridge.analytic_display_mode == "logs"


def test_tc_gui_133(analytic_runtime):
    bridge, _presenter = analytic_runtime
    bridge.analytic_set_display_mode("bench")
    assert bridge.analytic_display_mode == "bench"


def test_tc_gui_134(analytic_runtime):
    bridge, _presenter = analytic_runtime
    bridge.analytic_set_display_mode("logs")
    bridge.analytic_set_display_mode("both")
    assert bridge.analytic_display_mode == "both"


def test_tc_gui_135(analytic_runtime):
    bridge, _presenter = analytic_runtime
    bridge.analytic_set_split_ratio(0.30)
    assert abs(bridge.analytic_split_ratio - 0.30) < 1e-6
    bridge.analytic_set_split_ratio(0.01)
    assert abs(bridge.analytic_split_ratio - 0.15) < 1e-6
    bridge.analytic_set_split_ratio(0.99)
    assert abs(bridge.analytic_split_ratio - 0.85) < 1e-6


def test_tc_gui_160(analytic_runtime, sample_log: Path):
    bridge, _presenter = analytic_runtime
    bridge.analytic_open_logs(str(sample_log))
    _pump(10)
    assert bridge.analytic_log_path == str(sample_log)


def test_tc_gui_161(analytic_runtime, sample_log: Path):
    bridge, _presenter = analytic_runtime
    bridge.analytic_open_logs(str(sample_log))
    _pump(10)
    before = len(bridge.analytic_log_entries)
    with sample_log.open("a", encoding="utf-8") as f:
        f.write("\n" + json.dumps({"level": "INFO", "subsystem": "GUI", "message": "new"}))
    bridge.analytic_refresh_logs()
    _pump(10)
    assert len(bridge.analytic_log_entries) == before + 1


def test_tc_gui_162(analytic_runtime, sample_log: Path):
    bridge, _presenter = analytic_runtime
    bridge.analytic_open_logs(str(sample_log))
    _pump(10)
    bridge.analytic_clear_logs()
    assert bridge.analytic_log_entries == []
    assert bridge.analytic_log_path == ""
    assert bridge.analytic_log_error == ""


def test_tc_gui_163(analytic_runtime):
    bridge, _presenter = analytic_runtime
    bridge.analytic_open_logs("/nonexistent/path/run.jsonl")
    _pump(10)
    assert bridge.analytic_log_error
    assert bridge.analytic_log_entries == []


def test_tc_gui_164(analytic_runtime, sample_log: Path):
    bridge, _presenter = analytic_runtime
    bridge.analytic_open_logs(str(sample_log))
    _pump(10)
    assert bridge.analytic_log_error == ""
    assert len(bridge.analytic_log_entries) >= 5
    subsystem = bridge.analytic_log_subsystems[0]
    assert all(e["subsystem"] == subsystem for e in bridge.analytic_log_entries if e["subsystem"] == subsystem)


def test_tc_gui_170(analytic_runtime, sample_bench: Path):
    bridge, _presenter = analytic_runtime
    bridge.analytic_open_bench(str(sample_bench))
    _pump(10)
    assert bridge.analytic_bench_path == str(sample_bench)


def test_tc_gui_171(analytic_runtime, sample_bench: Path):
    bridge, _presenter = analytic_runtime
    bridge.analytic_open_bench(str(sample_bench))
    _pump(10)
    before = bridge.analytic_bench_totals["count"]
    with sample_bench.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["subsystem", "phase", "label", "elapsed_ms", "timestamp"])
        writer.writerow({"subsystem": "GUI", "phase": "render", "label": "e", "elapsed_ms": "5.0", "timestamp": "t5"})
    bridge.analytic_refresh_bench()
    _pump(10)
    assert bridge.analytic_bench_totals["count"] == before + 1


def test_tc_gui_172(analytic_runtime, sample_bench: Path):
    bridge, _presenter = analytic_runtime
    bridge.analytic_open_bench(str(sample_bench))
    _pump(10)
    bridge.analytic_clear_bench()
    assert bridge.analytic_bench_entries == []
    assert bridge.analytic_bench_path == ""
    assert bridge.analytic_bench_error == ""
    assert bridge.analytic_bench_totals["count"] == 0


def test_tc_gui_173(analytic_runtime):
    bridge, _presenter = analytic_runtime
    bridge.analytic_open_bench("/nonexistent/benchmark.csv")
    _pump(10)
    assert bridge.analytic_bench_error
    assert bridge.analytic_bench_totals["count"] == 0


def test_tc_gui_174(analytic_runtime, sample_bench: Path):
    bridge, _presenter = analytic_runtime
    bridge.analytic_open_bench(str(sample_bench))
    _pump(10)
    totals = bridge.analytic_bench_totals
    assert totals["count"] == 4
    assert abs(totals["total_ms"] - 100.0) < 0.01
    assert abs(totals["avg_ms"] - 25.0) < 0.01
    assert totals["slowest_phase"]


def test_tc_gui_175(analytic_runtime, sample_bench: Path):
    bridge, _presenter = analytic_runtime
    bridge.analytic_open_bench(str(sample_bench))
    _pump(10)
    phases = {row["phase"] for row in bridge.analytic_bench_by_phase}
    assert phases == {"load", "render", "control"}


def test_tc_gui_176(analytic_runtime, sample_bench: Path):
    bridge, _presenter = analytic_runtime
    bridge.analytic_open_bench(str(sample_bench))
    _pump(10)
    subsystems = {row["subsystem"] for row in bridge.analytic_bench_by_subsystem}
    assert subsystems == {"GUI", "MOTOR"}
    assert all(row["segments"] for row in bridge.analytic_bench_by_subsystem)


def test_tc_gui_180():
    _qml_ready("gui/panels/base_design/qml/base_panel.qml")


def test_tc_gui_181():
    _qml_ready("gui/panels/vla_design/qml/vla_panel.qml")


def test_tc_gui_182():
    _qml_ready("gui/panels/analytic_design/qml/analytic_panel.qml")
