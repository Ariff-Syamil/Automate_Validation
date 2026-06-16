"""Headless GUI presenter/bridge integration tests."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from gui.panels.analytic_design.view import AnalyticPanelBridge
from gui.panels.base_design.base_presenter import BasePanelPresenter
from gui.panels.base_design.base_view import BasePanelBridge
from gui.panels.vla_design.presenter import VlaPanelPresenter
from gui.panels.vla_design.view import VlaPanelBridge
from tests.framework.base import TestCaseFramework, scenario


class _ControllerSpy:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def apply_preview(self, **kwargs) -> None:
        self.calls.append(kwargs)

    def is_live(self) -> bool:
        return False

    def shutdown(self) -> None:
        return None


def _qapp():
    return QApplication.instance() or QApplication(sys.argv[:1])


class TestPresenterHandlers(TestCaseFramework):
    @scenario("base_presenter_motor_handlers", "Base motor handlers keep safe state")
    def test_base_presenter_motor_handlers(self) -> None:
        app = _qapp()
        bridge = BasePanelBridge()
        presenter = BasePanelPresenter(bridge)
        try:
            presenter.update_motor_data(0, 0, 100.0, "1 m/s", "1 mm", "1°", "1 Nm")
            bridge.base_motor_direction.emit(0, 0, -1)
            bridge.base_motor_mode.emit(0, 0, "speed")
            bridge.base_motor_target_rpm.emit(0, 0, 250.0)
            bridge.base_motor_estop.emit(0, 0)

            assert presenter._motor_states[0][0]["rpm"] == 0.0
            assert presenter._motor_states[0][0]["speed"] == "0 m/s"
        finally:
            presenter.shutdown()
            presenter.deleteLater()
            bridge.deleteLater()
            app.processEvents()

    @scenario("base_gesture_overlay", "Base gesture handlers update bridge overlay state")
    def test_base_gesture_overlay_handlers(self) -> None:
        app = _qapp()
        bridge = BasePanelBridge()
        presenter = BasePanelPresenter(bridge)
        try:
            presenter._gesture_controller.reset_tracking = lambda: None
            presenter._handle_gesture_motor_selected("ALL")
            presenter._handle_gesture_speed_changed(0.5)
            presenter._handle_gesture_stopped(True)
            bridge.base_gesture_reset_clicked.emit()

            assert bridge.base_gesture_motor_id == "ALL"
            assert bridge.base_gesture_speed == 0.5
            assert bridge.base_gesture_stopped is True
        finally:
            presenter.shutdown()
            presenter.deleteLater()
            bridge.deleteLater()
            app.processEvents()

    @scenario("vla_presenter_handlers", "VLA presenter prompt/transport/camera handlers")
    def test_vla_presenter_prompt_transport_and_camera(self) -> None:
        app = _qapp()
        bridge = VlaPanelBridge()
        presenter = VlaPanelPresenter(bridge)
        spy = _ControllerSpy()
        try:
            presenter._camera_controller = spy
            bridge.vla_start_clicked.emit()
            bridge.vla_prompt_submitted.emit("Pick up the red block")
            bridge.vla_motor_estop.emit(0, 0)
            bridge.vla_configure_clicked.emit(0, 0, 0, 15)

            assert presenter._motors_running is True
            assert presenter._motor_states[0][0]["rpm"] == 0.0
            if bridge.vla_mock_camera_enabled:
                assert bridge.vla_cam1_preview_live is True
            else:
                assert spy.calls and spy.calls[-1]["cam_mode"] == 0
        finally:
            presenter.deleteLater()
            bridge.deleteLater()
            app.processEvents()

    @scenario("analytics_data_flow", "Analytics bridge/presenter loads and clears files")
    def test_analytics_bridge_presenter_flow(self, tmp_path: Path) -> None:
        from gui.panels.analytic_design.presenter import AnalyticPanelPresenter

        app = _qapp()
        log_path = tmp_path / "run.jsonl"
        bench_path = tmp_path / "bench.csv"
        log_path.write_text(
            "\n".join(
                json.dumps({"ts": f"t{i}", "level": "INFO", "subsystem": "GUI", "message": f"m{i}"})
                for i in range(2)
            ),
            encoding="utf-8",
        )
        with bench_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["subsystem", "phase", "label", "elapsed_ms", "timestamp"])
            writer.writeheader()
            writer.writerow({"subsystem": "GUI", "phase": "load", "label": "a", "elapsed_ms": "5.0", "timestamp": "t"})
        bridge = AnalyticPanelBridge()
        presenter = AnalyticPanelPresenter(bridge)
        try:
            bridge.analytic_open_logs(str(log_path))
            bridge.analytic_open_bench(str(bench_path))
            app.processEvents()
            assert bridge.analytic_log_entries
            assert bridge.analytic_bench_entries
            bridge.analytic_clear_logs()
            bridge.analytic_clear_bench()
            assert bridge.analytic_log_entries == []
            assert bridge.analytic_bench_entries == []
        finally:
            presenter.deleteLater()
            bridge.deleteLater()
            app.processEvents()
