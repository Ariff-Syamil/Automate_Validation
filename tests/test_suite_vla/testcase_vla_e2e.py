"""VLA end-to-end smoke tests (Plan step 8).

Two scenarios from plan §4 step 8 — full chain exercised in mock mode:

- test_prompt_to_motor_e2e_mock
- test_tab_switch_e2e_mock

Real components used:

- ``VlaPanelBridge``                — signal contract
- ``VlaPanelPresenter``             — prompt handler, frame caching, playback
- ``NullVlaServerSupervisor``       — supervisor seam (always ``ready``)
- ``VlaInferenceWorker``            — QThread-based dispatch
- ``VlaClient(mock=True)``          — deterministic synthetic action chunk

Only the camera ``QVideoSink`` and ``QVideoFrame`` are stubbed; the
presenter consumes a real ``QImage`` produced by ``toImage()``.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from backend.vla_client import VlaClient
from backend.vla_config import load_vla_config
from backend.vla_server_supervisor import NullVlaServerSupervisor
from backend.vla_worker import VlaInferenceWorker
from gui.panels.vla_design.presenter import VlaPanelPresenter
from gui.panels.vla_design.view import VlaPanelBridge
from tests.framework.base import TestCaseFramework, scenario


# ── Stubs ────────────────────────────────────────────────────────────────


class _StubVideoSink(QObject):
    """Duck-types ``QVideoSink``: only ``videoFrameChanged`` is needed."""

    videoFrameChanged = Signal(object)


class _StubVideoFrame:
    """Duck-types ``QVideoFrame`` for the cached-frame path."""

    def __init__(self, image: QImage) -> None:
        self._image = image

    def isValid(self) -> bool:  # noqa: N802 — Qt naming
        return True

    def toImage(self) -> QImage:  # noqa: N802 — Qt naming
        return self._image


class _RecordingNullSupervisor(NullVlaServerSupervisor):
    """``NullVlaServerSupervisor`` that records ``stop()`` calls."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.stop_calls = 0

    def stop(self) -> None:
        self.stop_calls += 1
        super().stop()


# ── Helpers ──────────────────────────────────────────────────────────────


def _build_real_worker() -> VlaInferenceWorker:
    """Build a real worker forced into mock mode regardless of YAML state."""
    cfg = load_vla_config()
    joint_names = tuple(entry["joint_name"] for entry in cfg["joint_map"])
    client = VlaClient(
        host=cfg["policy_host"],
        port=cfg["policy_port"],
        joint_names=joint_names,
        action_horizon=cfg["action_horizon"],
        mock=True,
    )
    return VlaInferenceWorker(client)


def _build_presenter(
    *,
    supervisor=None,
    timer_interval_ms: int = 1,
):
    bridge = VlaPanelBridge()
    sup = supervisor if supervisor is not None else NullVlaServerSupervisor()
    worker = _build_real_worker()
    presenter = VlaPanelPresenter(bridge, supervisor=sup, worker=worker)
    presenter._action_timer.setInterval(timer_interval_ms)
    return bridge, sup, worker, presenter


def _push_synthetic_frame(bridge: VlaPanelBridge) -> QImage:
    """Register a stub sink with ``bridge`` and emit one synthetic frame."""
    sink = _StubVideoSink()
    bridge.vla_register_cam1_video_sink(sink)
    img = QImage(224, 224, QImage.Format.Format_RGB888)
    img.fill(0x336699)
    sink.videoFrameChanged.emit(_StubVideoFrame(img))
    return img


# ── Test class ───────────────────────────────────────────────────────────


class TestVlaEndToEndMock(TestCaseFramework):
    """End-to-end smoke through bridge → presenter → worker → playback."""

    @scenario(
        "prompt_to_motor_e2e_mock",
        "Full chain in mock mode drives all four motors; Stop halts the continuous loop cleanly",
    )
    def test_prompt_to_motor_e2e_mock(self, qtbot) -> None:
        bridge, supervisor, worker, presenter = _build_presenter()
        try:
            emissions: list[tuple[int, int, float]] = []
            bridge.vla_motor_angle_deg.connect(
                lambda node, motor, deg: emissions.append((node, motor, deg))
            )

            _push_synthetic_frame(bridge)
            qtbot.wait(30)  # let the throttle-and-cache closure run
            assert presenter._last_frame is not None, (
                "camera frame must be cached before submitting the prompt"
            )
            self.log("synthetic CAM1 frame cached on the presenter")

            bridge.vla_prompt_submitted.emit("test prompt")
            self.log("emitted vla_prompt_submitted; waiting for the arm to be driven")

            # Full chain: worker submit -> mock infer -> action_ready ->
            # QTimer playback drives motors 0-3. The continuous re-inference
            # loop keeps running, so wait until all four motors have been
            # driven at least once rather than for a (now perpetual) idle state.
            def _all_four_driven() -> bool:
                return {motor for _, motor, _ in emissions} >= {0, 1, 2, 3}

            qtbot.waitUntil(_all_four_driven, timeout=2000)
            assert presenter._vla_running is True, "continuous loop should be active mid-task"

            motors_seen = {motor for _, motor, _ in emissions if _ is not None}
            nodes_seen = {node for node, _, _ in emissions}
            self.log(
                f"received {len(emissions)} motor emissions; "
                f"motors={sorted(motors_seen)}, nodes={sorted(nodes_seen)}"
            )

            # Plan assertions
            assert motors_seen == {0, 1, 2, 3}, (
                f"expected at least one emission for each of motors 0-3; got {sorted(motors_seen)}"
            )
            assert nodes_seen == {0}, (
                f"only node 0 is driven; saw nodes {sorted(nodes_seen)}"
            )
            assert presenter._motor_states[0][0]["angle"] != "0°", (
                "node 0 motor 0 angle must have moved away from the initial '0°' label"
            )
            assert bridge.vla_gripper_state == "open", (
                f"gripper must stay 'open'; got {bridge.vla_gripper_state!r}"
            )

            # Stop ends the continuous loop and returns busy to idle.
            presenter._handle_stop_clicked()
            qtbot.waitUntil(lambda: bridge.vla_busy == "idle", timeout=2000)
            assert presenter._vla_running is False, "Stop must end the continuous loop"
            assert bridge.vla_busy == "idle", (
                f"vla_busy must return to 'idle' after Stop; got {bridge.vla_busy!r}"
            )
            assert bridge.vla_last_error == "", (
                f"vla_last_error must be empty after a successful run; got {bridge.vla_last_error!r}"
            )
        finally:
            presenter.shutdown()

    @scenario(
        "tab_switch_e2e_mock",
        "Submit then nav away: supervisor.stop() called and motor signals halt",
    )
    def test_tab_switch_e2e_mock(self, qtbot) -> None:
        # Use a moderate playback rate so the test can observe playback
        # being interrupted mid-flight by the section change.
        supervisor = _RecordingNullSupervisor()
        bridge, _, worker, presenter = _build_presenter(
            supervisor=supervisor,
            timer_interval_ms=30,  # ~30 Hz playback so 8 steps last ~240 ms
        )
        try:
            _push_synthetic_frame(bridge)
            qtbot.wait(30)
            assert presenter._last_frame is not None

            emissions: list[tuple[int, int, float]] = []
            bridge.vla_motor_angle_deg.connect(
                lambda node, motor, deg: emissions.append((node, motor, deg))
            )

            bridge.vla_prompt_submitted.emit("test prompt")
            # Let the worker dispatch and at least one playback tick fire.
            qtbot.wait(80)
            before_switch = len(emissions)
            self.log(f"{before_switch} motor emissions before nav-away")
            assert before_switch > 0, (
                "playback must have produced at least one emission before nav-away"
            )

            stops_before = supervisor.stop_calls
            bridge.vla_active_section = "base"

            # Generous post-switch window for any queued events to drain.
            qtbot.wait(400)

            self.log(
                f"after nav-away: stop_calls={supervisor.stop_calls}, "
                f"total emissions={len(emissions)} (was {before_switch})"
            )
            assert supervisor.stop_calls > stops_before, (
                "supervisor.stop() must be called on nav-away from the VLA panel"
            )
            assert len(emissions) == before_switch, (
                f"no motor signals must fire after nav-away; "
                f"got {len(emissions) - before_switch} extra"
            )
            assert bridge.vla_busy == "idle"
        finally:
            presenter.shutdown()
