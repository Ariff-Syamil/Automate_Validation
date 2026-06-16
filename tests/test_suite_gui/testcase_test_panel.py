"""Headless tests for the in-app TEST panel runner and bridge wiring.

These do not open a window; they exercise the bridge slots, the QTimer-
driven runner, and the gesture-test generator using the ``QApplication``
created by ``conftest.qapp_gui`` and pumped with ``app.processEvents()``.

The full end-to-end "run the gesture test against the mock video" path is
covered manually (see plan ``verification`` section); here we only assert
that the wiring is sound so a broken slot/signal contract is caught in CI.
"""

from __future__ import annotations

import sys
import time

from PySide6.QtCore import QElapsedTimer
from PySide6.QtWidgets import QApplication

from tests.framework.base import TestCaseFramework, scenario
from tests._paths import AUTOMATE5_ROOT


def _pump(app: QApplication, ms: int) -> None:
    """Spin the event loop for ``ms`` milliseconds."""
    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < ms:
        app.processEvents()


class TestAutomatedTestPanel(TestCaseFramework):
    """Bridge-level coverage for the admin TEST overlay."""

    # ── REGISTRY / LISTING ────────────────────────────────────────────────

    @scenario("test_panel_registry", "TestRunner registers the gesture case and the bridge lists it")
    def test_runner_registry(self) -> None:
        from gui.automation.test_runner import build_default_runner
        from gui.panels.base_design.base_view import BasePanelBridge

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = BasePanelBridge()
        runner = build_default_runner(parent=bridge)
        bridge.attach_test_runner(runner)

        cases = bridge.base_list_test_cases()
        ids = {c["id"] for c in cases}
        self.log(f"registered cases: {sorted(ids)}")
        for expected in ("gesture_detection", "gesture_left", "gesture_right", "service_lifecycle"):
            assert expected in ids, f"{expected!r} must be registered by build_default_runner()"

        bridge.deleteLater()
        app.processEvents()

    # ── TEST CONTROLLER (panel-agnostic overlay backing) ─────────────────

    @scenario("test_controller_surface", "TestController exposes runner+supervisor under generic names; empty runner is harmless")
    def test_test_controller_surface(self) -> None:
        """The overlay binds to a TestController, not a panel bridge. Verify the
        generic surface works for a populated runner and that an empty runner
        (the VLA panel, which has no test cases yet) yields an empty, no-op
        controller rather than an error."""
        from backend.services import RestartPolicy, ServiceName, ServiceSupervisor
        from backend.services.simulated import SimulatedCameraService
        from gui.automation.test_controller import TestController
        from gui.automation.test_runner import CameraSource, TestRunner, build_default_runner
        from gui.panels.base_design.base_view import BasePanelBridge

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = BasePanelBridge()

        # Populated controller (Base-style).
        runner = build_default_runner(parent=bridge)
        sup = ServiceSupervisor(parent=bridge)
        sup.register(ServiceName.CAMERA, lambda: SimulatedCameraService(), policy=RestartPolicy.none())
        ctrl = TestController(bridge=bridge, runner=runner, supervisor=sup, parent=bridge)

        ids = {c["id"] for c in ctrl.list_test_cases()}
        assert "gesture_detection" in ids and "service_lifecycle" in ids
        assert ctrl.run_test_case("does_not_exist", CameraSource.MOCK.value) is False
        assert any(r["name"] == "camera" for r in ctrl.service_snapshot())

        # Empty controller (VLA-style — no cases registered yet, no supervisor).
        empty = TestController(bridge=bridge, runner=TestRunner(parent=bridge), supervisor=None, parent=bridge)
        assert empty.list_test_cases() == []
        assert empty.service_snapshot() == []
        assert empty.run_test_case("anything", "mock") is False
        assert empty.test_case_running is False
        self.log("test_test_controller_surface: OK")

        bridge.deleteLater()
        app.processEvents()

    # ── SHARED LOG MODEL ──────────────────────────────────────────────────

    @scenario("shared_log_model", "Shared LogListModel appends, exposes roles, caps, and clears")
    def test_shared_log_model(self) -> None:
        from gui.shared.log_model import LogListModel, get_shared_log_model

        m = LogListModel(max_entries=3)
        assert m.rowCount() == 0

        m.appendEntry("00:00:01", "TEST", "one")
        m.appendEntry("00:00:02", "INFO", "two")
        assert m.rowCount() == 2

        idx0 = m.index(0, 0)
        assert m.data(idx0, LogListModel.MessageRole) == "one"
        assert m.data(idx0, LogListModel.LevelRole) == "TEST"
        assert m.data(idx0, LogListModel.TimestampRole) == "00:00:01"

        # Role names match the InspectorDock delegate (timestamp/level/message).
        roles = {bytes(v) for v in m.roleNames().values()}
        assert {b"timestamp", b"level", b"message"} <= roles

        # Bounded: adding past max_entries drops the oldest rows.
        m.appendEntry("3", "INFO", "three")
        m.appendEntry("4", "INFO", "four")
        assert m.rowCount() == 3
        assert m.data(m.index(0, 0), LogListModel.MessageRole) == "two", "oldest row should drop"

        m.clear()
        assert m.rowCount() == 0

        # Singleton identity — every panel binds to the same instance.
        assert get_shared_log_model() is get_shared_log_model()
        self.log("test_shared_log_model: OK")

    # ── POSE-VIDEO FORCING + GESTURE CAPTURE ──────────────────────────────

    @scenario("test_panel_pose_video_forcing", "MOCK source points slot 0 at the requested gui-folder hand video")
    def test_pose_video_forcing(self) -> None:
        """apply_camera_source(mock_video=...) must force mock on and set
        slot 0 to the file URL of the requested video (the LeftHand /
        RightHand gesture clips), not the default mock_camera.mp4."""
        from pathlib import Path

        from gui.automation.test_runner import CameraSource, GuiDriver
        from gui.panels.base_design.base_view import BasePanelBridge

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = BasePanelBridge()

        repo_root = AUTOMATE5_ROOT
        left_video = repo_root / "gui" / "assets" / "LeftHand_GestureVideo.mp4"

        right_video = repo_root / "gui" / "assets" / "RightHand_GestureVideo.mp4"

        d = GuiDriver(bridge, CameraSource.MOCK)
        d.apply_camera_source(mock_video=str(left_video))
        assert bridge.base_mock_camera_enabled is True
        src = bridge.base_mock_camera_source_1
        assert "LeftHand_GestureVideo" in src, f"expected LeftHand video URL, got {src}"

        # set_mock_video re-points slot 0 (used after configure to lock the clip).
        d.set_mock_video(str(right_video))
        src2 = bridge.base_mock_camera_source_1
        assert "RightHand_GestureVideo" in src2, f"expected RightHand video URL, got {src2}"
        d.restore_camera_source()

        bridge.deleteLater()
        app.processEvents()

    @scenario("test_panel_gesture_capture", "GuiDriver records motor-id, speed span, and fist-stop from bridge signals")
    def test_gesture_capture_plumbing(self) -> None:
        """begin_gesture_capture subscribes to the bridge gesture signals;
        driving the bridge properties must update the driver's observations."""
        from gui.automation.test_runner import CameraSource, GuiDriver
        from gui.panels.base_design.base_view import BasePanelBridge

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = BasePanelBridge()
        d = GuiDriver(bridge, CameraSource.MOCK)

        d.begin_gesture_capture()
        # Left-hand: motor selection.
        bridge.base_gesture_motor_id = "3"
        bridge.base_gesture_motor_id = "ALL"
        # Right-hand: speed sweep low then high.
        bridge.base_gesture_speed = 0.05
        bridge.base_gesture_speed = 0.95
        # Right-hand: fist stop.
        bridge.base_gesture_stopped = True
        app.processEvents()

        assert d.seen_motor_ids() == {"3", "ALL"}, d.seen_motor_ids()
        assert d.speed_min() <= 0.2 and d.speed_max() >= 0.8, (d.speed_min(), d.speed_max())
        assert d.stop_seen() is True
        d.end_gesture_capture()

        # After end, further changes must not be recorded.
        bridge.base_gesture_motor_id = "1"
        app.processEvents()
        assert "1" not in d.seen_motor_ids(), "capture should have stopped after end_gesture_capture"

        bridge.deleteLater()
        app.processEvents()

    # ── RUN PATH (synthetic bridge state) ─────────────────────────────────

    @scenario("test_panel_run_synthetic", "Runner reaches PASS when bridge state satisfies the gesture predicates")
    def test_runner_pass_with_synthetic_state(self) -> None:
        """Drive the runner without the real camera pipeline.

        We start the gesture scenario and then immediately set the two
        bridge properties the predicate watches (``base_cam1_preview_live``
        and ``base_gesture_frame_size``) so the generator advances through
        every wait and emits a PASS result.
        """
        from gui.automation.test_runner import CameraSource, build_default_runner
        from gui.panels.base_design.base_view import BasePanelBridge

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = BasePanelBridge()
        runner = build_default_runner(parent=bridge)
        bridge.attach_test_runner(runner)

        results: list[tuple[bool, str]] = []
        bridge.base_test_case_result.connect(lambda ok, msg: results.append((ok, msg)))

        # Pretend the camera went live immediately and the gesture worker
        # reported a frame size before the runner's first tick.
        bridge.base_cam1_preview_live = True
        bridge.base_set_gesture_frame_size(1280, 720)

        started = bridge.base_run_test_case("gesture_detection", CameraSource.MOCK.value)
        assert started, "runner refused to start"
        assert bridge.base_test_case_running, "running flag should be True after start"

        # The runner ticks every 100 ms; give it plenty of time.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not results:
            app.processEvents()
            time.sleep(0.05)

        assert results, "runner emitted no result within 5s"
        passed, summary = results[-1]
        self.log(f"result: passed={passed} summary={summary!r}")
        assert passed, f"expected PASS, got: {summary}"
        assert not bridge.base_test_case_running, "running flag should clear after result"

        bridge.deleteLater()
        app.processEvents()

    @scenario("test_panel_gesture_drives_services", "A gesture run drives the supervisor camera+gesture services for the snapshot")
    def test_gesture_run_drives_services(self) -> None:
        """With a supervisor attached, running a gesture scenario must move the
        camera and gesture services out of IDLE (so the Service Snapshot
        reflects activity), then return them to IDLE on teardown."""
        from backend.services import RestartPolicy, ServiceName, ServiceSupervisor
        from backend.services.simulated import (
            SimulatedCameraService,
            SimulatedGestureService,
            SimulatedVlaService,
        )
        from gui.automation.test_runner import CameraSource, build_default_runner
        from gui.panels.base_design.base_view import BasePanelBridge

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = BasePanelBridge()
        runner = build_default_runner(parent=bridge)
        bridge.attach_test_runner(runner)

        sup = ServiceSupervisor(parent=bridge)
        sup.register(ServiceName.CAMERA, lambda: SimulatedCameraService(), policy=RestartPolicy.none())
        sup.register(ServiceName.VLA, lambda: SimulatedVlaService(), policy=RestartPolicy.none())
        sup.register(
            ServiceName.GESTURE,
            lambda: SimulatedGestureService(),
            policy=RestartPolicy.none(),
            requires=ServiceName.CAMERA,
        )
        bridge.attach_supervisor(sup)

        seen: dict[str, set] = {}
        bridge.base_service_state_changed.connect(
            lambda name, state: seen.setdefault(name, set()).add(state)
        )
        results: list[tuple[bool, str]] = []
        bridge.base_test_case_result.connect(lambda ok, msg: results.append((ok, msg)))

        # Satisfy the gesture_detection predicates synthetically.
        bridge.base_cam1_preview_live = True
        bridge.base_set_gesture_frame_size(1280, 720)

        assert bridge.base_run_test_case("gesture_detection", CameraSource.MOCK.value)
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline and not results:
            app.processEvents()
            time.sleep(0.05)

        assert results and results[-1][0], f"gesture run should pass: {results}"
        self.log(f"service states seen: { {k: sorted(v) for k, v in seen.items()} }")
        for svc in ("camera", "gesture"):
            assert svc in seen and (seen[svc] & {"starting", "running"}), (
                f"{svc} should have left IDLE during the gesture run; saw {seen.get(svc)}"
            )

        bridge.deleteLater()
        app.processEvents()

    # ── CANCEL PATH ───────────────────────────────────────────────────────

    @scenario("test_panel_cancel", "Cancellation surfaces a FAIL result and clears the running flag")
    def test_runner_cancel(self) -> None:
        from gui.automation.test_runner import CameraSource, build_default_runner
        from gui.panels.base_design.base_view import BasePanelBridge

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = BasePanelBridge()
        runner = build_default_runner(parent=bridge)
        bridge.attach_test_runner(runner)

        results: list[tuple[bool, str]] = []
        bridge.base_test_case_result.connect(lambda ok, msg: results.append((ok, msg)))

        # Do NOT satisfy any predicate — the runner will sit in the first
        # WaitUntil. Cancel immediately and confirm a FAIL is emitted.
        assert bridge.base_run_test_case("gesture_detection", CameraSource.MOCK.value)
        bridge.base_cancel_test_case()

        _pump(app, 500)
        assert results, "expected a result after cancellation"
        passed, summary = results[-1]
        self.log(f"cancel result: passed={passed} summary={summary!r}")
        assert not passed
        assert "Cancel" in summary or "cancel" in summary

        bridge.deleteLater()
        app.processEvents()

    # ── CAMERA SOURCE FORCING (item 3) ────────────────────────────────────

    @scenario("test_panel_mock_source_forcing", "MOCK source forces mock-camera mode and the gui-folder video")
    def test_camera_source_forcing(self) -> None:
        """The overlay's MOCK toggle must force the bundled mock video on,
        regardless of the YAML camera_enabled flag, and restore the prior
        state afterwards. CONFIGURED must force mock off."""
        from gui.automation.test_runner import CameraSource, GuiDriver
        from gui.panels.base_design.base_view import BasePanelBridge

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = BasePanelBridge()

        original = bool(bridge.base_mock_camera_enabled)
        mock_url0 = bridge.base_mock_camera_url_at(0)
        assert mock_url0, "expected at least one mock video URL from config"
        assert "mock_camera" in mock_url0, f"expected gui-folder mock video, got {mock_url0}"

        # MOCK: forces enabled True and points slot 0 at the mock video.
        d_mock = GuiDriver(bridge, CameraSource.MOCK)
        d_mock.apply_camera_source()
        assert bridge.base_mock_camera_enabled is True
        assert bridge.base_mock_camera_source_1 == mock_url0
        d_mock.restore_camera_source()
        assert bridge.base_mock_camera_enabled == original

        # CONFIGURED: forces mock off so the hardware path is taken.
        d_cfg = GuiDriver(bridge, CameraSource.CONFIGURED)
        d_cfg.apply_camera_source()
        assert bridge.base_mock_camera_enabled is False
        d_cfg.restore_camera_source()
        assert bridge.base_mock_camera_enabled == original

        self.log(f"camera source forcing OK (original={original}, mock_url={mock_url0})")
        bridge.deleteLater()
        app.processEvents()

    # ── SERVICE LIFECYCLE END-TO-END ──────────────────────────────────────

    @scenario("test_panel_service_lifecycle", "ServiceLifecycleTest passes against simulated services through the runner")
    def test_service_lifecycle_end_to_end(self) -> None:
        """Full pipeline: bridge → supervisor → runner → simulated workers.

        Builds a bridge, attaches a supervisor populated with the three
        simulated services, and runs the in-app ``service_lifecycle``
        scenario. Verifies the runner reaches a PASS result, which proves
        every wire of the supervisor integration is correct.
        """
        from backend.services import (
            RestartPolicy,
            ServiceName,
            ServiceSupervisor,
        )
        from backend.services.simulated import (
            SimulatedCameraService,
            SimulatedGestureService,
            SimulatedVlaService,
        )
        from gui.automation.test_runner import CameraSource, build_default_runner
        from gui.panels.base_design.base_view import BasePanelBridge

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = BasePanelBridge()
        runner = build_default_runner(parent=bridge)
        bridge.attach_test_runner(runner)

        sup = ServiceSupervisor(parent=bridge)
        sup.register(ServiceName.CAMERA, lambda: SimulatedCameraService(), policy=RestartPolicy.none())
        sup.register(ServiceName.VLA, lambda: SimulatedVlaService(), policy=RestartPolicy.none())
        sup.register(
            ServiceName.GESTURE,
            lambda: SimulatedGestureService(),
            policy=RestartPolicy.none(),
            requires=ServiceName.CAMERA,
        )
        bridge.attach_supervisor(sup)

        results: list[tuple[bool, str]] = []
        bridge.base_test_case_result.connect(lambda ok, msg: results.append((ok, msg)))

        assert bridge.base_run_test_case("service_lifecycle", CameraSource.MOCK.value)

        # Lifecycle test allows up to ~25s for start+stop on three services.
        deadline = time.monotonic() + 25.0
        while time.monotonic() < deadline and not results:
            app.processEvents()
            time.sleep(0.05)

        assert results, "service_lifecycle test did not finish within 25s"
        passed, summary = results[-1]
        self.log(f"service_lifecycle result: passed={passed} summary={summary!r}")
        assert passed, f"expected PASS, got: {summary}"

        bridge.deleteLater()
        app.processEvents()

    # ── UNKNOWN ID ────────────────────────────────────────────────────────

    @scenario("test_panel_unknown_id", "Unknown case id surfaces a FAIL result without crashing")
    def test_runner_unknown_case_id(self) -> None:
        from gui.automation.test_runner import CameraSource, build_default_runner
        from gui.panels.base_design.base_view import BasePanelBridge

        app = QApplication.instance() or QApplication(sys.argv[:1])
        bridge = BasePanelBridge()
        runner = build_default_runner(parent=bridge)
        bridge.attach_test_runner(runner)

        results: list[tuple[bool, str]] = []
        bridge.base_test_case_result.connect(lambda ok, msg: results.append((ok, msg)))

        started = bridge.base_run_test_case("does_not_exist", CameraSource.MOCK.value)
        assert started is False
        _pump(app, 100)
        assert results and results[-1][0] is False

        bridge.deleteLater()
        app.processEvents()
