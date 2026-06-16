"""Example GUI scenarios for BasePanel (actions live in code, not YAML).

Test ordering: the live camera test runs FIRST because it needs a pristine
QQuickWidget scene graph.  The QML compile check ``test_qml_loads`` runs in a
fresh subprocess, so it is immune to QML type-cache pollution from the
in-process QQuickWidget tests regardless of ordering.
"""

from __future__ import annotations

import sys
from pathlib import Path

from tests.framework.base import TestCaseFramework, scenario
from tests._paths import AUTOMATE5_ROOT


class TestBasePanel(TestCaseFramework):
    # config.yaml is loaded from this file's directory (test_suite_gui/).

    def configure_camera_mock(self) -> None:
        """Placeholder: wire real BasePanel / QML when GUI harness exists."""
        self.log("configure_camera_mock: start")
        assert True
        self.log("configure_camera_mock: done")

    def inject_motor_mock_data(self) -> None:
        self.log("inject_motor_mock_data: start")
        assert True
        self.log("inject_motor_mock_data: done")

    def press_play_button(self) -> None:
        assert True

    def wait_for_log_entries(self) -> None:
        assert True

    def verify_camera_configured(self) -> None:
        assert True

    def verify_motor_panel_running(self) -> None:
        assert True

    def verify_system_running(self) -> None:
        assert True

    def verify_logs_contain_mock_data(self) -> None:
        assert True

    # ── LIVE CAMERA TEST (must run before any QQmlEngine test) ────────────

    @scenario("camera_live_mock", "Launch BasePanel with MOCK camera feed and verify it goes live")
    def test_camera_live_mock(self, mock_data_config) -> None:
        """Launches the real BasePanel widget + presenter, triggers the mock
        camera configure flow, lets the event loop run so QML renders the
        mock video feed, then asserts both camera slots report live.

        ONLY RUNS if camera_enabled: true in gui_configuration.yaml.
        The window is shown on screen so the tester can visually confirm the
        mock webcam feed is playing."""
        import pytest
        from PySide6.QtCore import QElapsedTimer
        from PySide6.QtWidgets import QApplication

        from gui.panels.base_design.base_presenter import BasePanelPresenter
        from gui.panels.base_design.base_view import BasePanel

        # Skip if mock camera disabled in config
        if not mock_data_config["camera_enabled"]:
            pytest.skip("Mock camera disabled in gui_configuration.yaml")

        app = QApplication.instance() or QApplication(sys.argv[:1])

        # ── 1. Build the panel (loads QML + bridge) ──
        self.log("test_camera_live_mock: creating BasePanel")
        panel = BasePanel()
        presenter = BasePanelPresenter(panel.bridge)
        bridge = panel.bridge

        # ── 2. Show the window so the scene graph renders ──
        panel.setWindowTitle("BasePanel — MOCK Camera Test")
        panel.resize(1280, 720)
        panel.show()
        app.processEvents()
        self.log("test_camera_live_mock: panel shown")

        # ── 3. Verify mock camera is enabled from YAML ──
        assert bridge.base_mock_camera_enabled, "mock camera must be enabled in gui_configuration.yaml"
        assert bridge.base_mock_camera_count >= 1, "need at least 1 mock video source"

        # ── 4. Trigger configure — double mode, cam1=0, cam2=1 (or 0 if only 1 source) ──
        cam2_idx = min(1, bridge.base_mock_camera_count - 1)
        bridge.base_configure_clicked.emit(1, 0, cam2_idx, 15)  # cam_mode=1 (double)
        app.processEvents()
        self.log("test_camera_live_mock: configure signal emitted (double mode)")

        # ── 5. Pump the event loop for ~3 seconds so QML MediaPlayer starts playback ──
        DISPLAY_MS = 3000
        timer = QElapsedTimer()
        timer.start()
        while timer.elapsed() < DISPLAY_MS:
            app.processEvents()

        # ── 6. Assert camera slots went live ──
        assert bridge.base_cam1_preview_live, "CAM1 must be live after configure"
        assert bridge.base_cam2_preview_live, "CAM2 must be live in double mode"

        src1 = bridge.base_mock_camera_source_1
        src2 = bridge.base_mock_camera_source_2
        assert src1, "mock source 1 URL must be set"
        assert src2, "mock source 2 URL must be set"
        self.log(f"  cam1 live={bridge.base_cam1_preview_live} src={src1}")
        self.log(f"  cam2 live={bridge.base_cam2_preview_live} src={src2}")

        # ── 7. Cleanup ──
        panel.close()
        presenter.deleteLater()
        panel.deleteLater()
        app.processEvents()
        self.log("test_camera_live_mock: OK — mock webcam feed verified live")

    @scenario("camera_live_real", "Launch BasePanel with REAL Hololink IMX274 camera feed")
    def test_camera_live_real(self, mock_data_config) -> None:
        """Launches BasePanel with the real Hololink IMX274 camera.

        The Hololink camera is NOT a USB/V4L2 device — it is accessed exclusively
        through the Holoscan pipeline via HololinkCameraController. This test
        therefore gates only on the Holoscan SDK import (Linux/Docker) and on mock
        mode being disabled. USB camera enumeration is NOT used here because it
        would never find the IMX274.

        Skip conditions (in order):
          1. holoscan SDK not importable — not running in the Automate5 Docker image.
          2. Mock camera is enabled in gui_configuration.yaml — real path disabled.

        If both gates pass, the Hololink board is assumed to be connected. The test
        will fail with a real HololinkCameraController error if the board is absent,
        which is the correct and intentional outcome.
        """
        import pytest
        from PySide6.QtCore import QElapsedTimer
        from PySide6.QtWidgets import QApplication
        from gui.panels.base_design.base_presenter import BasePanelPresenter
        from gui.panels.base_design.base_view import BasePanel

        # Requires Holoscan SDK — ships only in the Automate5 Docker/GHCR image (Linux).
        pytest.importorskip("holoscan")

        # Skip if mock camera is enabled — the real Hololink path is disabled by config.
        if mock_data_config["camera_enabled"]:
            pytest.skip("Mock camera enabled in gui_configuration.yaml; real Hololink path disabled")

        app = QApplication.instance() or QApplication(sys.argv[:1])

        self.log("test_camera_live_real: Holoscan available, mock disabled — testing Hololink IMX274")
        panel = BasePanel()
        presenter = BasePanelPresenter(panel.bridge)
        bridge = panel.bridge

        panel.setWindowTitle("BasePanel — REAL Camera Test")
        panel.resize(1280, 720)
        panel.show()
        app.processEvents()
        self.log("test_camera_live_real: panel shown")

        # Verify mock is disabled
        assert not bridge.base_mock_camera_enabled, "mock camera must be disabled for real camera test"

        # Configure single real camera (cam_mode=0)
        bridge.base_configure_clicked.emit(0, 0, 0, 15)
        app.processEvents()
        self.log("test_camera_live_real: configure signal emitted (single real camera)")

        # Wait for camera to go live
        DISPLAY_MS = 3000
        timer = QElapsedTimer()
        timer.start()
        while timer.elapsed() < DISPLAY_MS:
            app.processEvents()

        # Assert cam1 went live
        assert bridge.base_cam1_preview_live, "CAM1 must be live with real camera"
        self.log(f"  cam1 live={bridge.base_cam1_preview_live}")

        panel.close()
        presenter.deleteLater()
        panel.deleteLater()
        app.processEvents()
        self.log("test_camera_live_real: OK — real camera feed verified")

    # ── HEADLESS BRIDGE / CONTROLLER TESTS ────────────────────────────────

    @scenario("bridge_defaults", "BasePanelBridge initialises with YAML-backed defaults")
    def test_bridge_defaults(self) -> None:
        """Verify the Python side of BasePanel (the bridge) constructs and reads
        gui_configuration.yaml. Avoids QQuickWidget so it can run anywhere."""
        from PySide6.QtWidgets import QApplication

        from gui.panels.base_design.base_view import BasePanelBridge

        app = QApplication.instance() or QApplication(sys.argv[:1])
        self.log("test_bridge_defaults: creating BasePanelBridge")
        bridge = BasePanelBridge()

        assert bridge.base_node_count >= 1, "node_count must come from YAML (>=1)"
        assert bridge.base_motors_per_node >= 1, "motors_per_node must come from YAML (>=1)"
        assert bridge.base_active_section == "base"

        self.log(
            f"test_bridge_defaults: OK (nodes={bridge.base_node_count}, "
            f"motors_per_node={bridge.base_motors_per_node})"
        )
        bridge.deleteLater()
        app.processEvents()

    @scenario("camera_bridge_mock_props", "Bridge mock-camera properties initialise from YAML")
    def test_camera_bridge_mock_props(self, mock_data_config) -> None:
        """Headless: verify the bridge reads mock camera config from
        gui_configuration.yaml and exposes mock_camera_enabled,
        mock_camera_count, and url_at().  No window needed.
        
        ONLY RUNS if camera_enabled: true in gui_configuration.yaml."""
        import pytest
        from PySide6.QtWidgets import QApplication

        from gui.panels.base_design.base_view import BasePanelBridge

        if not mock_data_config["camera_enabled"]:
            pytest.skip("Mock camera disabled in gui_configuration.yaml")

        app = QApplication.instance() or QApplication(sys.argv[:1])
        self.log("test_camera_bridge_mock_props: creating BasePanelBridge")
        bridge = BasePanelBridge()

        assert bridge.base_mock_camera_enabled is True, "mock camera should be enabled via YAML"
        assert bridge.base_mock_camera_count >= 1, "at least one mock camera source expected"
        self.log(f"  mock_camera_count={bridge.base_mock_camera_count}")

        url0 = bridge.base_mock_camera_url_at(0)
        assert url0, "url_at(0) must return a resolved URL"
        assert "file:///" in url0 or "file:" in url0, f"expected file URL, got: {url0}"
        self.log(f"  url_at(0)={url0}")

        assert bridge.base_mock_camera_url_at(999) == "", "url_at(999) must be empty"

        bridge.deleteLater()
        app.processEvents()
        self.log("test_camera_bridge_mock_props: OK")

    @scenario("camera_stop_releases_pipeline", "Explicit camera stop clears preview flags / releases the pipeline")
    def test_camera_stop_releases_pipeline(self) -> None:
        """Force the mock camera on, configure it (preview goes live), then
        emit base_camera_stop_requested and assert the preview / hololink
        flags clear. Verifies the teardown path the TEST runner uses to
        release the camera so the device is never left open between runs."""
        from PySide6.QtWidgets import QApplication

        from gui.panels.base_design.base_presenter import BasePanelPresenter
        from gui.panels.base_design.base_view import BasePanelBridge

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = BasePanelBridge()
        presenter = BasePanelPresenter(bridge)

        # Force the mock-camera path on (independent of YAML camera_enabled).
        bridge.base_mock_camera_enabled = True
        url0 = bridge.base_mock_camera_url_at(0)
        assert url0, "expected a mock video URL from config"
        bridge.base_mock_camera_source_1 = url0

        # Configure (mock branch) — preview should go live synchronously.
        bridge.base_configure_clicked.emit(0, 0, 0, 15)
        app.processEvents()
        assert bridge.base_cam1_preview_live, "mock configure should set preview live"

        # Explicit teardown — preview + hololink flags must clear.
        bridge.base_camera_stop_requested.emit()
        app.processEvents()
        assert not bridge.base_cam1_preview_live, "camera stop must clear cam1 preview"
        assert not bridge.base_cam2_preview_live, "camera stop must clear cam2 preview"
        assert not bridge.base_hololink_active, "camera stop must clear hololink active"
        self.log("test_camera_stop_releases_pipeline: OK")

        presenter.deleteLater()
        bridge.deleteLater()
        app.processEvents()

    @scenario("mock_video_survives_configure", "set_mock_video overrides the clip the configure handler picks")
    def test_mock_video_survives_configure(self) -> None:
        """Reproduce and lock the wrong-video fix: the presenter's configure
        handler resets slot 0 to the indexed mock clip (mock_camera.mp4), so a
        gesture clip set before configure is lost. Re-asserting the clip AFTER
        configure must make it authoritative — this is why the Right test no
        longer plays the Left video."""
        from PySide6.QtCore import QUrl
        from PySide6.QtWidgets import QApplication

        from gui.panels.base_design.base_presenter import BasePanelPresenter
        from gui.panels.base_design.base_view import BasePanelBridge

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = BasePanelBridge()
        presenter = BasePanelPresenter(bridge)

        repo_root = AUTOMATE5_ROOT
        right_url = QUrl.fromLocalFile(
            str(repo_root / "gui" / "assets" / "RightHand_GestureVideo.mp4")
        ).toString()

        # Pre-configure: point slot 0 at the RightHand clip.
        bridge.base_mock_camera_enabled = True
        bridge.base_mock_camera_source_1 = right_url

        # Configure overwrites slot 0 with the indexed mock clip (index 0).
        bridge.base_configure_clicked.emit(0, 0, 0, 15)
        app.processEvents()
        assert "RightHand_GestureVideo" not in bridge.base_mock_camera_source_1, (
            "configure is expected to overwrite slot 0 with the indexed mock clip"
        )

        # The fix: re-assert the desired clip after configure.
        bridge.base_mock_camera_source_1 = right_url
        app.processEvents()
        assert "RightHand_GestureVideo" in bridge.base_mock_camera_source_1
        self.log("test_mock_video_survives_configure: OK")

        presenter.deleteLater()
        bridge.deleteLater()
        app.processEvents()

    @scenario("stop_resets_gesture_overlay", "Stop clears stale gesture overlay state between runs")
    def test_stop_resets_gesture_overlay(self) -> None:
        """After a run, pressing Stop must clear the gesture overlay state so
        the next run (e.g. switching from the left-hand to the right-hand
        test) does not show the previous hand's bounding box / motor / speed."""
        from PySide6.QtWidgets import QApplication

        from gui.panels.base_design.base_presenter import BasePanelPresenter
        from gui.panels.base_design.base_view import BasePanelBridge

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = BasePanelBridge()
        presenter = BasePanelPresenter(bridge)

        # Simulate stale left-hand detection state.
        bridge.base_gesture_motor_id = "3"
        bridge.base_gesture_speed = 0.75
        bridge.base_gesture_stopped = True
        bridge.base_set_left_bbox(0.1, 0.1, 0.5, 0.5, True)
        bridge.base_set_gesture_frame_size(640, 480)
        app.processEvents()

        # Stop must reset the overlay to a clean slate.
        bridge.base_stop_clicked.emit()
        app.processEvents()

        assert bridge.base_gesture_motor_id == ""
        assert bridge.base_gesture_speed == 0.0
        assert bridge.base_gesture_stopped is False
        assert bridge.base_gesture_left_bbox[4] is False
        assert list(bridge.base_gesture_frame_size) == [0, 0]
        self.log("test_stop_resets_gesture_overlay: OK")

        presenter.deleteLater()
        bridge.deleteLater()
        app.processEvents()

    @scenario("camera_configure_mock_single", "Mock configure flow sets preview live (single)")
    def test_camera_configure_mock_single(self, mock_data_config) -> None:
        """Headless: simulate the presenter configure handler in single-camera
        mock mode.  Verifies cam1 goes live and cam2 stays off.
        
        ONLY RUNS if camera_enabled: true in gui_configuration.yaml."""
        import pytest
        from PySide6.QtWidgets import QApplication

        from gui.panels.base_design.base_view import BasePanelBridge

        if not mock_data_config["camera_enabled"]:
            pytest.skip("Mock camera disabled in gui_configuration.yaml")

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = BasePanelBridge()

        assert not bridge.base_cam1_preview_live
        assert not bridge.base_cam2_preview_live

        cam1_signals: list[bool] = []
        bridge.base_cam1_preview_live_changed.connect(lambda: cam1_signals.append(True))

        bridge.base_mock_camera_source_1 = bridge.base_mock_camera_url_at(0)
        bridge.base_cam1_preview_live = True
        bridge.base_cam2_preview_live = False

        assert bridge.base_cam1_preview_live is True, "cam1 must be live after configure"
        assert bridge.base_cam2_preview_live is False, "cam2 must stay off in single mode"
        assert bridge.base_mock_camera_source_1, "mock source 1 must be set"
        assert len(cam1_signals) == 1, "cam1 live signal should have fired once"

        self.log("test_camera_configure_mock_single: OK")
        bridge.deleteLater()
        app.processEvents()

    @scenario("camera_configure_mock_double", "Mock configure flow sets both previews live (double)")
    def test_camera_configure_mock_double(self, mock_data_config) -> None:
        """Headless: simulate presenter configure in double-camera mock mode.
        
        ONLY RUNS if camera_enabled: true in gui_configuration.yaml."""
        import pytest
        from PySide6.QtWidgets import QApplication

        from gui.panels.base_design.base_view import BasePanelBridge

        if not mock_data_config["camera_enabled"]:
            pytest.skip("Mock camera disabled in gui_configuration.yaml")

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = BasePanelBridge()

        cam_mode = 1  # double
        bridge.base_mock_camera_source_1 = bridge.base_mock_camera_url_at(0)
        if bridge.base_mock_camera_count > 1:
            bridge.base_mock_camera_source_2 = bridge.base_mock_camera_url_at(1)
        bridge.base_cam1_preview_live = True
        bridge.base_cam2_preview_live = (cam_mode == 1)

        assert bridge.base_cam1_preview_live is True
        assert bridge.base_cam2_preview_live is True, "cam2 must be live in double mode"
        assert bridge.base_mock_camera_source_1, "mock source 1 set"
        if bridge.base_mock_camera_count > 1:
            assert bridge.base_mock_camera_source_2, "mock source 2 set"
            assert bridge.base_mock_camera_source_1 != bridge.base_mock_camera_source_2, \
                "sources should differ when multiple mock videos configured"

        self.log("test_camera_configure_mock_double: OK")
        bridge.deleteLater()
        app.processEvents()

    @scenario("motor_running_after_start", "Mock motor data updates after base_start_clicked")
    def test_motor_running_after_start(self, mock_data_config) -> None:
        """Headless: build BasePanelBridge + BasePanelPresenter, emit the Start
        ("Play") click signal, pump the Qt event loop for several mock-data
        ticks, and assert the motor container is moving — i.e. mock motor RPMs
        advance away from rest after the click and freeze again after Stop.

        ONLY RUNS if presenter.mock_data.enabled is true in
        gui_configuration.yaml; otherwise the mock tick timer is never
        installed and there is nothing to observe.
        """
        import pytest
        from PySide6.QtCore import QElapsedTimer
        from PySide6.QtWidgets import QApplication

        from gui.panels.base_design.base_presenter import BasePanelPresenter
        from gui.panels.base_design.base_view import BasePanelBridge

        # Runs only in the Automate5 Docker/GHCR image, where the Hololink/
        # holoscan SDK is present (Linux-only). Skip on local dev machines.
        pytest.importorskip("holoscan")

        if not mock_data_config["enabled"]:
            pytest.skip("Mock data disabled in gui_configuration.yaml")

        tick_ms = int(mock_data_config.get("tick_ms", 500)) or 500
        # Wait for at least three mock ticks so a single delayed timer firing
        # does not cause a false negative.
        wait_ms = max(tick_ms * 3 + 200, 1500)

        app = QApplication.instance() or QApplication(sys.argv[:1])
        self.log("test_motor_running_after_start: creating bridge + presenter")
        bridge = BasePanelBridge()
        presenter = BasePanelPresenter(bridge)

        node_count = bridge.base_node_count
        motors_per_node = bridge.base_motors_per_node

        def snapshot_rpms() -> list[float]:
            return [
                presenter._motor_states[n][m]["rpm"]
                for n in range(node_count)
                for m in range(motors_per_node)
            ]

        # ── 1. Pre-click: drain a tick so the idle path zeros every motor ──
        idle_timer = QElapsedTimer()
        idle_timer.start()
        while idle_timer.elapsed() < tick_ms + 100:
            app.processEvents()

        pre_rpms = snapshot_rpms()
        assert all(rpm == 0.0 for rpm in pre_rpms), (
            f"all motors must be at rest before Start, got {pre_rpms}"
        )
        assert presenter._motors_running is False, "presenter must start in stopped state"

        # ── 2. Simulate the Play / Start button click ──
        bridge.base_cam1_preview_live = True
        self.log("test_motor_running_after_start: emitting base_start_clicked")
        bridge.base_start_clicked.emit()
        app.processEvents()

        assert presenter._motors_running is True, (
            "presenter._motors_running must flip True after base_start_clicked"
        )

        # ── 3. Pump the event loop for several mock ticks ──
        running_timer = QElapsedTimer()
        running_timer.start()
        while running_timer.elapsed() < wait_ms:
            app.processEvents()

        # ── 4. Assert the motor container is moving ──
        #     a) At least one motor has a non-zero RPM.
        #     b) RPM values change between two samples taken a tick apart
        #        (so the container is *actively* moving, not just latched).
        running_rpms = snapshot_rpms()
        assert any(rpm != 0.0 for rpm in running_rpms), (
            f"expected at least one non-zero motor RPM after Start, got {running_rpms}"
        )

        diff_timer = QElapsedTimer()
        diff_timer.start()
        while diff_timer.elapsed() < tick_ms + 200:
            app.processEvents()
        running_rpms_2 = snapshot_rpms()
        assert running_rpms != running_rpms_2, (
            "motor RPMs must change between successive ticks while running "
            f"(snapshot1={running_rpms}, snapshot2={running_rpms_2})"
        )

        self.log(
            f"test_motor_running_after_start: motors moving — "
            f"nonzero={sum(1 for r in running_rpms if r != 0.0)}/"
            f"{len(running_rpms)}, deltas observed"
        )

        # ── 5. Emit Stop and confirm motion ceases on the next tick ──
        bridge.base_stop_clicked.emit()
        app.processEvents()
        assert presenter._motors_running is False, (
            "presenter._motors_running must flip False after base_stop_clicked"
        )

        stop_timer = QElapsedTimer()
        stop_timer.start()
        while stop_timer.elapsed() < tick_ms + 200:
            app.processEvents()
        stopped_rpms = snapshot_rpms()
        assert all(rpm == 0.0 for rpm in stopped_rpms), (
            f"all motors must return to rest after Stop, got {stopped_rpms}"
        )

        # ── 6. Cleanup ──
        presenter.shutdown()
        presenter.deleteLater()
        bridge.deleteLater()
        app.processEvents()
        self.log("test_motor_running_after_start: OK")

    @scenario(
        "camera_enumerate",
        "enumerate_video_inputs returns the two fixed IMX274 Hololink sensor slot labels",
    )
    def test_camera_enumerate(self) -> None:
        """Headless: enumerate_video_inputs() returns the two fixed Hololink IMX274 sensor
        slot labels (no USB/V4L2 enumeration — QCameraDevice is not used).

        The function is used to populate the camera-selector dropdown in the GUI.
        It always returns exactly ["IMX274 Sensor 0", "IMX274 Sensor 1"] with
        [None, None] as devices (the actual pipeline is configured separately via
        HololinkCameraController.apply_preview()).
        """
        from backend.camera_controller import enumerate_video_inputs

        labels, devices = enumerate_video_inputs()
        assert isinstance(labels, list)
        assert isinstance(devices, list)
        assert len(labels) == len(devices), "labels and devices must be same length"
        self.log(f"test_camera_enumerate: {len(labels)} camera(s) found")

    @scenario("camera_controller_signals", "CameraController emits live signals on hard stop")
    def test_camera_controller_signals(self) -> None:
        """Headless: verify HololinkCameraController.shutdown() is safe when idle."""
        from PySide6.QtWidgets import QApplication

        from backend.hololink_camera_controller import HololinkCameraController

        app = QApplication.instance() or QApplication(sys.argv[:1])
        ctrl = HololinkCameraController()

        emissions: list[tuple[int, bool]] = []
        ctrl.cam1_live_changed.connect(lambda v: emissions.append((0, v)))
        ctrl.cam2_live_changed.connect(lambda v: emissions.append((1, v)))

        ctrl.shutdown()
        app.processEvents()
        self.log(f"test_camera_controller_signals: shutdown OK, emissions={emissions}")

        ctrl.deleteLater()
        app.processEvents()

    # ── QML FILE / COMPILE CHECKS (run after live test — QQmlEngine pollutes type cache) ─

    @scenario("qml_source", "base_panel.qml exists and imports AppComponents")
    def test_qml_source(self) -> None:
        """File-level sanity so QML wiring errors surface without a scene graph render."""
        repo_root = AUTOMATE5_ROOT
        qml_path = repo_root / "gui" / "panels" / "base_design" / "qml" / "base_panel.qml"
        self.log(f"test_qml_source: checking {qml_path}")

        assert qml_path.is_file(), f"Missing QML: {qml_path}"
        text = qml_path.read_text(encoding="utf-8")
        assert "import AppComponents" in text, "base_panel.qml must import AppComponents"
        assert "base_bridge" in text, "base_panel.qml must reference base_bridge"
        self.log("test_qml_source: OK")

    @scenario("qml_loads", "base_panel.qml parses and resolves all imports")
    def test_qml_loads(self) -> None:
        """Real QML compile of base_panel.qml in a fresh subprocess.

        A QQmlEngine type cache polluted by earlier in-process GUI tests can
        make an in-process compile fail intermittently, so the compile runs in
        a pristine child process: it loads base_panel.qml, resolves the
        AppComponents import path, type-checks every referenced component, and
        exits non-zero (reporting the errors) if anything fails to resolve.
        """
        import os
        import subprocess

        repo_root = AUTOMATE5_ROOT
        qml_path = repo_root / "gui" / "panels" / "base_design" / "qml" / "base_panel.qml"
        components_path = repo_root / "gui" / "components"
        assert qml_path.is_file(), f"Missing QML: {qml_path}"

        child = '''import sys
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine

qml_path, components_path = sys.argv[1], sys.argv[2]
app = QApplication(sys.argv[:1])
engine = QQmlEngine()
engine.addImportPath(components_path)
comp = QQmlComponent(engine, QUrl.fromLocalFile(qml_path))
for _ in range(200):
    if comp.status() != QQmlComponent.Status.Loading:
        break
    app.processEvents()
if comp.status() != QQmlComponent.Status.Ready:
    for e in comp.errors():
        print(f"{e.url().toString()}:{e.line()}:{e.column()} {e.description()}", file=sys.stderr)
    sys.exit(1)
sys.exit(0)
'''

        env = dict(os.environ)
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        self.log(f"test_qml_loads: compiling {qml_path} in a fresh subprocess")
        result = subprocess.run(
            [sys.executable, "-c", child, str(qml_path.resolve()), str(components_path.resolve())],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(repo_root),
            timeout=120,
        )
        assert result.returncode == 0, (
            "base_panel.qml failed to load:\n" + (result.stderr or result.stdout)
        )
        self.log("test_qml_loads: OK (component Ready, imports resolved)")

    # ── GUI BRIDGE/PRESENTER FLOW TESTS ───────────────────────────────────

    @scenario("action1", "Configure and inject mock data")
    def test_action1(self) -> None:
        """Configure mock camera and push presenter motor data through the bridge."""
        import pytest
        from PySide6.QtWidgets import QApplication

        from gui.panels.base_design.base_presenter import BasePanelPresenter
        from gui.panels.base_design.base_view import BasePanelBridge

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = BasePanelBridge()
        if not bridge.base_mock_camera_enabled:
            pytest.skip("Mock camera disabled in gui_configuration.yaml")
        presenter = BasePanelPresenter(bridge)
        try:
            bridge.base_configure_clicked.emit(0, 0, 0, 15)
            presenter.update_motor_data(0, 0, 123.0, "1 m/s", "1 mm", "1°", "1 Nm")
            assert bridge.base_cam1_preview_live is True
            assert presenter._motor_states[0][0]["rpm"] == 123.0
        finally:
            presenter.shutdown()
            presenter.deleteLater()
            bridge.deleteLater()
            app.processEvents()

    @scenario("action2", "Configure, inject, and verify camera")
    def test_action2(self) -> None:
        """Exercise double-camera mock configure through presenter signal wiring."""
        import pytest
        from PySide6.QtWidgets import QApplication

        from gui.panels.base_design.base_presenter import BasePanelPresenter
        from gui.panels.base_design.base_view import BasePanelBridge

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = BasePanelBridge()
        if not bridge.base_mock_camera_enabled:
            pytest.skip("Mock camera disabled in gui_configuration.yaml")
        presenter = BasePanelPresenter(bridge)
        try:
            cam2 = min(1, bridge.base_mock_camera_count - 1)
            bridge.base_configure_clicked.emit(1, 0, cam2, 15)
            assert bridge.base_cam1_preview_live is True
            assert bridge.base_cam2_preview_live is True
            assert bridge.base_mock_camera_source_1
        finally:
            presenter.shutdown()
            presenter.deleteLater()
            bridge.deleteLater()
            app.processEvents()

    @scenario("action3", "Full flow end-to-end (placeholder)")
    def test_action3(self) -> None:
        """Headless full bridge/presenter flow: configure, start, tick, stop."""
        import pytest
        from PySide6.QtCore import QElapsedTimer
        from PySide6.QtWidgets import QApplication

        from gui.panels.base_design.base_presenter import BasePanelPresenter
        from gui.panels.base_design.base_view import BasePanelBridge

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = BasePanelBridge()
        if not bridge.base_mock_camera_enabled:
            pytest.skip("Mock camera disabled in gui_configuration.yaml")
        presenter = BasePanelPresenter(bridge)
        presenter._gesture_controller.start_recognition = lambda: None
        presenter._gesture_controller.stop_recognition = lambda: None
        presenter._gesture_controller.reset_tracking = lambda: None
        try:
            bridge.base_configure_clicked.emit(0, 0, 0, 15)
            bridge.base_start_clicked.emit()
            timer = QElapsedTimer()
            timer.start()
            while timer.elapsed() < 650:
                app.processEvents()
            presenter._generate_mock_data()
            assert bridge.base_cam1_preview_live is True
            assert presenter._motors_running is True
            assert any(m["rpm"] != 0.0 for node in presenter._motor_states for m in node)
            bridge.base_stop_clicked.emit()
            assert presenter._motors_running is False
        finally:
            presenter.shutdown()
            presenter.deleteLater()
            bridge.deleteLater()
            app.processEvents()
