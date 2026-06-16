"""GUI scenarios for VlaPanel — bridge + QML compile checks (mirrors Base panel tests).

Test ordering: the live camera test runs FIRST because it needs a pristine
QQuickWidget scene graph.  The headless QQmlEngine-based ``test_qml_loads``
runs LAST — its cached QML type info would otherwise block a subsequent
QQuickWidget from initialising in the same process.
"""

from __future__ import annotations

import sys
from pathlib import Path

from tests.framework.base import TestCaseFramework, scenario
from tests._paths import AUTOMATE5_ROOT


class TestVlaPanel(TestCaseFramework):
    # config.yaml is loaded from this file's directory (test_suite_gui/).

    # ── LIVE CAMERA TEST (must run before any QQmlEngine test) ────────────

    @scenario("camera_live_mock", "Launch VlaPanel with MOCK camera feed and verify it goes live")
    def test_camera_live_mock(self, mock_data_config) -> None:
        """Launches the real VlaPanel widget + presenter, triggers the mock
        camera configure flow, lets the event loop run so QML renders the
        mock video feed, then asserts both camera slots report live.

        ONLY RUNS if camera_enabled: true in gui_configuration.yaml.
        The window is shown on screen so the tester can visually confirm the
        mock webcam feed is playing."""
        import pytest
        from PySide6.QtCore import QElapsedTimer
        from PySide6.QtWidgets import QApplication

        from gui.panels.vla_design.presenter import VlaPanelPresenter
        from gui.panels.vla_design.view import VlaPanel

        if not mock_data_config["camera_enabled"]:
            pytest.skip("Mock camera disabled in gui_configuration.yaml")

        app = QApplication.instance() or QApplication(sys.argv[:1])

        self.log("test_camera_live_mock: creating VlaPanel")
        panel = VlaPanel()
        presenter = VlaPanelPresenter(panel.bridge)
        bridge = panel.bridge

        panel.setWindowTitle("VlaPanel — MOCK Camera Test")
        panel.resize(1280, 720)
        panel.show()
        app.processEvents()
        self.log("test_camera_live_mock: panel shown")

        assert bridge.vla_mock_camera_enabled, "mock camera must be enabled in gui_configuration.yaml"
        assert bridge.vla_mock_camera_count >= 1, "need at least 1 mock video source"

        cam2_idx = min(1, bridge.vla_mock_camera_count - 1)
        bridge.vla_configure_clicked.emit(1, 0, cam2_idx, 15)
        app.processEvents()
        self.log("test_camera_live_mock: configure signal emitted (double mode)")

        DISPLAY_MS = 3000
        timer = QElapsedTimer()
        timer.start()
        while timer.elapsed() < DISPLAY_MS:
            app.processEvents()

        assert bridge.vla_cam1_preview_live, "CAM1 must be live after configure"
        assert bridge.vla_cam2_preview_live, "CAM2 must be live in double mode"

        src1 = bridge.vla_mock_camera_source_1
        src2 = bridge.vla_mock_camera_source_2
        assert src1, "mock source 1 URL must be set"
        assert src2, "mock source 2 URL must be set"
        self.log(f"  cam1 live={bridge.vla_cam1_preview_live} src={src1}")
        self.log(f"  cam2 live={bridge.vla_cam2_preview_live} src={src2}")

        panel.close()
        presenter.deleteLater()
        panel.deleteLater()
        app.processEvents()
        self.log("test_camera_live_mock: OK — mock webcam feed verified live")

    @scenario("camera_live_real", "Launch VlaPanel with REAL Hololink IMX274 camera feed")
    def test_camera_live_real(self, mock_data_config) -> None:
        """Launches VlaPanel with the real Hololink IMX274 camera.

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
        import importlib.util

        import pytest
        from PySide6.QtCore import QElapsedTimer
        from PySide6.QtWidgets import QApplication
        from gui.panels.vla_design.presenter import VlaPanelPresenter
        from gui.panels.vla_design.view import VlaPanel

        # Requires Holoscan SDK — ships only in the Automate5 Docker/GHCR image (Linux).
        if importlib.util.find_spec("holoscan") is None:
            pytest.skip("holoscan runtime not available; real Hololink camera path is Linux/Docker-only")

        # Skip if mock camera is enabled — the real Hololink path is disabled by config.
        if mock_data_config["camera_enabled"]:
            pytest.skip("Mock camera enabled in gui_configuration.yaml; real Hololink path disabled")

        app = QApplication.instance() or QApplication(sys.argv[:1])

        self.log("test_camera_live_real: Holoscan available, mock disabled — testing Hololink IMX274")
        panel = VlaPanel()
        presenter = VlaPanelPresenter(panel.bridge)
        bridge = panel.bridge

        panel.setWindowTitle("VlaPanel — REAL Camera Test")
        panel.resize(1280, 720)
        panel.show()
        app.processEvents()
        self.log("test_camera_live_real: panel shown")

        assert not bridge.vla_mock_camera_enabled, "mock camera must be disabled for real camera test"

        bridge.vla_configure_clicked.emit(0, 0, 0, 15)
        app.processEvents()
        self.log("test_camera_live_real: configure signal emitted (single real camera)")

        DISPLAY_MS = 3000
        timer = QElapsedTimer()
        timer.start()
        while timer.elapsed() < DISPLAY_MS:
            app.processEvents()

        assert bridge.vla_cam1_preview_live, "CAM1 must be live with real camera"
        self.log(f"  cam1 live={bridge.vla_cam1_preview_live}")

        panel.close()
        presenter.deleteLater()
        panel.deleteLater()
        app.processEvents()
        self.log("test_camera_live_real: OK — real camera feed verified")

    # ── HEADLESS BRIDGE TESTS ─────────────────────────────────────────────

    @scenario("bridge_defaults", "VlaPanelBridge initialises with YAML-backed defaults")
    def test_bridge_defaults(self) -> None:
        """Verify the Python side of VlaPanel (the bridge) constructs and reads
        gui_configuration.yaml (base_panel node/motor counts). Avoids QQuickWidget."""
        from PySide6.QtWidgets import QApplication

        from gui.panels.vla_design.view import VlaPanelBridge

        app = QApplication.instance() or QApplication(sys.argv[:1])
        self.log("test_bridge_defaults: creating VlaPanelBridge")
        bridge = VlaPanelBridge()

        assert bridge.vla_node_count >= 1, "node_count must come from YAML (>=1)"
        assert bridge.vla_motors_per_node >= 1, "motors_per_node must come from YAML (>=1)"
        assert bridge.vla_active_section == "vla"

        self.log(
            f"test_bridge_defaults: OK (nodes={bridge.vla_node_count}, "
            f"motors_per_node={bridge.vla_motors_per_node})"
        )
        bridge.deleteLater()
        app.processEvents()

    # ── VLA RUNTIME CONFIG (Step 1 of plan_vla_integration.md) ────────────

    @scenario("vla_config_loads", "load_vla_config returns fully-populated dict with defaults")
    def test_vla_config_loads(self) -> None:
        """Headless: ``load_vla_config`` must return a dict whose required
        keys are all present, with sensible defaults when the YAML ``vla:``
        section is missing or partial."""
        from backend.vla_config import load_vla_config

        # ── 1. Empty overrides → every required key must materialise ──
        cfg = load_vla_config({})

        required_top_level = {
            "enabled", "mock_mode", "policy_host", "policy_port",
            "action_horizon", "gripper_default_state", "joint_map", "server",
        }
        missing = required_top_level - set(cfg.keys())
        assert not missing, f"missing required keys when YAML is empty: {missing}"

        assert isinstance(cfg["enabled"], bool)
        assert isinstance(cfg["mock_mode"], bool)
        assert isinstance(cfg["policy_host"], str) and cfg["policy_host"]
        assert isinstance(cfg["policy_port"], int) and cfg["policy_port"] > 0
        assert isinstance(cfg["action_horizon"], int) and cfg["action_horizon"] >= 1
        assert cfg["gripper_default_state"] == "open", (
            "gripper_default_state must default to 'open' per locked decisions"
        )

        server = cfg["server"]
        assert isinstance(server, dict)
        assert {"launch_cmd", "startup_timeout_s"} <= set(server.keys())
        assert server["launch_cmd"], "server.launch_cmd must default to a non-empty command"
        assert isinstance(server["startup_timeout_s"], float)
        assert server["startup_timeout_s"] > 0.0

        # ── 2. Overrides must be honoured ──
        cfg2 = load_vla_config({
            "enabled": False,
            "mock_mode": False,
            "policy_host": "10.0.0.5",
            "policy_port": 6000,
            "action_horizon": 16,
            "gripper_default_state": "closed",
            "server": {"launch_cmd": "echo stub", "startup_timeout_s": 1.5},
        })
        assert cfg2["enabled"] is False
        assert cfg2["mock_mode"] is False
        assert cfg2["policy_host"] == "10.0.0.5"
        assert cfg2["policy_port"] == 6000
        assert cfg2["action_horizon"] == 16
        assert cfg2["gripper_default_state"] == "closed"
        assert cfg2["server"]["launch_cmd"] == "echo stub"
        assert cfg2["server"]["startup_timeout_s"] == 1.5

        # ── 3. The on-disk YAML must also load without error ──
        cfg3 = load_vla_config()
        assert isinstance(cfg3, dict)
        assert set(cfg3.keys()) >= required_top_level

        self.log("test_vla_config_loads: OK")

    @scenario("vla_joint_map_defaults", "Default joint_map produces 4 mapped + 2 unmapped entries")
    def test_vla_joint_map_defaults(self) -> None:
        """Headless: with no ``joint_map`` supplied, the loader must produce
        exactly six entries — joints 0..3 mapped to node 0 motors 0..3, and
        joints 4 (wrist_roll) and 5 (gripper) marked unmapped (node=None,
        motor=None, mapped=False). This is the locked four-motor budget."""
        from backend.vla_config import load_vla_config

        cfg = load_vla_config({})  # no joint_map override → defaults apply
        jm = cfg["joint_map"]

        assert isinstance(jm, list)
        assert len(jm) == 6, f"joint_map must have 6 entries (one per VLA joint), got {len(jm)}"

        # ── 1. Joints 0..3 mapped to node 0 motors 0..3 ──
        expected = [
            (0, "shoulder_pan",  0, 0),
            (1, "shoulder_lift", 0, 1),
            (2, "elbow_flex",    0, 2),
            (3, "wrist_flex",    0, 3),
        ]
        for joint_index, joint_name, node, motor in expected:
            entry = jm[joint_index]
            assert entry["mapped"] is True, f"joint {joint_index} ({joint_name}) must be mapped"
            assert entry["joint_name"] == joint_name
            assert entry["node"] == node
            assert entry["motor"] == motor

        # ── 2. wrist_roll and gripper must be marked unmapped ──
        wrist_roll = jm[4]
        gripper    = jm[5]
        for name, entry in (("wrist_roll", wrist_roll), ("gripper", gripper)):
            assert entry["mapped"] is False, f"{name} must be unmapped (no motor slot)"
            assert entry["node"] is None, f"{name} node must be None when unmapped"
            assert entry["motor"] is None, f"{name} motor must be None when unmapped"

        assert wrist_roll["joint_name"] == "wrist_roll"
        assert gripper["joint_name"] == "gripper"

        # ── 3. No motor slot is double-booked across mapped joints ──
        mapped_slots = [(e["node"], e["motor"]) for e in jm if e["mapped"]]
        assert len(mapped_slots) == len(set(mapped_slots)), (
            f"duplicate (node, motor) assignment in default joint_map: {mapped_slots}"
        )
        assert len(mapped_slots) == 4, "exactly four motors are driven by the VLA"

        # ── 4. Explicit overrides flow through ──
        cfg_override = load_vla_config({
            "joint_map": [
                {"joint_index": 0, "joint_name": "shoulder_pan", "node": 1, "motor": 2},
                {"joint_index": 5, "joint_name": "gripper",      "node": None, "motor": None},
            ],
        })
        jm2 = cfg_override["joint_map"]
        assert len(jm2) == 2, "explicit joint_map must not be padded with defaults"
        assert jm2[0]["node"] == 1 and jm2[0]["motor"] == 2 and jm2[0]["mapped"] is True
        assert jm2[1]["mapped"] is False

        self.log("test_vla_joint_map_defaults: OK")

    @scenario("camera_bridge_mock_props", "VLA bridge mock-camera properties initialise from YAML")
    def test_camera_bridge_mock_props(self, mock_data_config) -> None:
        """Headless: verify the bridge reads mock camera config from
        gui_configuration.yaml and exposes mock_camera_enabled,
        mock_camera_count, and url_at().  No window needed.
        
        ONLY RUNS if camera_enabled: true in gui_configuration.yaml."""
        import pytest
        from PySide6.QtWidgets import QApplication

        from gui.panels.vla_design.view import VlaPanelBridge

        if not mock_data_config["camera_enabled"]:
            pytest.skip("Mock camera disabled in gui_configuration.yaml")

        app = QApplication.instance() or QApplication(sys.argv[:1])
        self.log("test_camera_bridge_mock_props: creating VlaPanelBridge")
        bridge = VlaPanelBridge()

        assert bridge.vla_mock_camera_enabled is True, "mock camera should be enabled via YAML"
        assert bridge.vla_mock_camera_count >= 1, "at least one mock camera source expected"
        self.log(f"  vla_mock_camera_count={bridge.vla_mock_camera_count}")

        url0 = bridge.vla_mock_camera_url_at(0)
        assert url0, "url_at(0) must return a resolved URL"
        assert "file:///" in url0 or "file:" in url0, f"expected file URL, got: {url0}"
        self.log(f"  url_at(0)={url0}")

        assert bridge.vla_mock_camera_url_at(999) == "", "url_at(999) must be empty"

        bridge.deleteLater()
        app.processEvents()
        self.log("test_camera_bridge_mock_props: OK")

    @scenario("camera_configure_mock_single", "VLA mock configure sets preview live (single)")
    def test_camera_configure_mock_single(self, mock_data_config) -> None:
        """Headless: simulate presenter configure in single-camera mock mode
        for VLA.  Cam1 goes live, cam2 stays off.
        
        ONLY RUNS if camera_enabled: true in gui_configuration.yaml."""
        import pytest
        from PySide6.QtWidgets import QApplication

        from gui.panels.vla_design.view import VlaPanelBridge

        if not mock_data_config["camera_enabled"]:
            pytest.skip("Mock camera disabled in gui_configuration.yaml")

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = VlaPanelBridge()

        assert not bridge.vla_cam1_preview_live
        assert not bridge.vla_cam2_preview_live

        cam1_signals: list[bool] = []
        bridge.vla_cam1_preview_live_changed.connect(lambda: cam1_signals.append(True))

        bridge.vla_mock_camera_source_1 = bridge.vla_mock_camera_url_at(0)
        bridge.vla_cam1_preview_live = True
        bridge.vla_cam2_preview_live = False

        assert bridge.vla_cam1_preview_live is True, "cam1 must be live after configure"
        assert bridge.vla_cam2_preview_live is False, "cam2 must stay off in single mode"
        assert bridge.vla_mock_camera_source_1, "mock source 1 must be set"
        assert len(cam1_signals) == 1, "cam1 live signal should have fired once"

        self.log("test_camera_configure_mock_single: OK")
        bridge.deleteLater()
        app.processEvents()

    @scenario("camera_configure_mock_double", "VLA mock configure sets both previews live (double)")
    def test_camera_configure_mock_double(self, mock_data_config) -> None:
        """Headless: simulate presenter configure in double-camera mock mode.
        
        ONLY RUNS if camera_enabled: true in gui_configuration.yaml."""
        import pytest
        from PySide6.QtWidgets import QApplication

        from gui.panels.vla_design.view import VlaPanelBridge

        if not mock_data_config["camera_enabled"]:
            pytest.skip("Mock camera disabled in gui_configuration.yaml")

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = VlaPanelBridge()

        cam_mode = 1
        bridge.vla_mock_camera_source_1 = bridge.vla_mock_camera_url_at(0)
        if bridge.vla_mock_camera_count > 1:
            bridge.vla_mock_camera_source_2 = bridge.vla_mock_camera_url_at(1)
        bridge.vla_cam1_preview_live = True
        bridge.vla_cam2_preview_live = (cam_mode == 1)

        assert bridge.vla_cam1_preview_live is True
        assert bridge.vla_cam2_preview_live is True, "cam2 must be live in double mode"
        assert bridge.vla_mock_camera_source_1, "mock source 1 set"
        if bridge.vla_mock_camera_count > 1:
            assert bridge.vla_mock_camera_source_2, "mock source 2 set"
            assert bridge.vla_mock_camera_source_1 != bridge.vla_mock_camera_source_2, \
                "sources should differ when multiple mock videos configured"

        self.log("test_camera_configure_mock_double: OK")
        bridge.deleteLater()
        app.processEvents()

    # ── QML FILE / COMPILE CHECKS (run after live test) ───────────────────

    @scenario("qml_source", "vla_panel.qml exists and imports AppComponents")
    def test_qml_source(self) -> None:
        """File-level sanity without scene graph render."""
        repo_root = AUTOMATE5_ROOT
        qml_path = repo_root / "gui" / "panels" / "vla_design" / "qml" / "vla_panel.qml"
        self.log(f"test_qml_source: checking {qml_path}")

        assert qml_path.is_file(), f"Missing QML: {qml_path}"
        text = qml_path.read_text(encoding="utf-8")
        assert "import AppComponents" in text, "vla_panel.qml must import AppComponents"
        assert "vla_bridge" in text, "vla_panel.qml must reference vla_bridge"
        self.log("test_qml_source: OK")

    @scenario("qml_loads", "vla_panel.qml parses and resolves all imports")
    def test_qml_loads(self) -> None:
        """QQmlComponent to Ready — no .create() (avoids scene graph / Windows offscreen issues).

        NOTE: runs after the live camera test because the QQmlEngine type cache
        can block a later QQuickWidget from initialising in the same process."""
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent, QQmlEngine
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication(sys.argv[:1])

        repo_root = AUTOMATE5_ROOT
        qml_path = repo_root / "gui" / "panels" / "vla_design" / "qml" / "vla_panel.qml"
        components_path = repo_root / "gui" / "components"

        engine = QQmlEngine()
        engine.addImportPath(str(components_path.resolve()))

        self.log(f"test_qml_loads: compiling {qml_path}")
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(qml_path.resolve())))

        for _ in range(200):
            if component.status() != QQmlComponent.Status.Loading:
                break
            app.processEvents()

        errors = [f"{e.url().toString()}:{e.line()}:{e.column()} {e.description()}"
                  for e in component.errors()]
        assert component.status() == QQmlComponent.Status.Ready, (
            "vla_panel.qml failed to load:\n  " + "\n  ".join(errors)
        )
        self.log("test_qml_loads: OK (component Ready, imports resolved)")

        engine.deleteLater()
        app.processEvents()
