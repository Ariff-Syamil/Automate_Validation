"""VLA action-chunk playback tests (Plan step 6).

Four scenarios from plan §4 step 6:

- test_action_chunk_emits_four_motor_gauge_signals
- test_wrist_roll_excluded_from_gauge_display
- test_gripper_held_open
- test_action_chunk_updates_motor_states

Background
----------
The SO-101 arm has 6 joints (shoulder_pan, shoulder_lift, elbow_flex,
wrist_flex, wrist_roll, gripper).  The GR00T policy produces a (T, 6)
action chunk and write_goal() forwards ALL 6 positions to the physical arm.

The GUI, however, renders only 4 motor angle gauges (joints 0-3).
``wrist_roll`` (index 4) is excluded from the ``vla_motor_angle_deg``
signal stream — it is still written to the arm, just not displayed as a
gauge.  ``gripper`` (index 5) is surfaced separately via
``vla_gripper_state_changed`` (open / closed), not as an angle value.

The presenter is constructed with stub supervisor and worker so the action
playback path is exercised in isolation; the action timer interval is
patched to 1 ms in each test so an eight-step chunk plays out in well
under 100 ms.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from gui.panels.vla_design.presenter import VlaPanelPresenter
from gui.panels.vla_design.view import VlaPanelBridge
from tests.framework.base import TestCaseFramework, scenario


# ── Stubs ────────────────────────────────────────────────────────────────


class _StubSupervisor(QObject):
    state_changed        = Signal(str)
    state_detail_changed = Signal(str)
    started              = Signal()
    start_failed         = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = "ready"
        self._state_detail = ""

    @property
    def state(self) -> str:
        return self._state

    @property
    def state_detail(self) -> str:
        return self._state_detail

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def reset(self) -> None:
        pass


class _StubWorker(QObject):
    action_ready = Signal(object)
    error_occurred = Signal(str)

    def submit(self, prompt, frame_rgb, joint_state) -> int:  # noqa: ARG002
        return 1

    def cancel(self) -> None:
        pass

    def shutdown(self) -> None:
        pass


# ── Helpers ──────────────────────────────────────────────────────────────


def _build_presenter():
    bridge = VlaPanelBridge()
    presenter = VlaPanelPresenter(
        bridge,
        supervisor=_StubSupervisor(),
        worker=_StubWorker(),
    )
    # Speed up the QTimer-paced playback so tests run in milliseconds.
    presenter._action_timer.setInterval(1)
    # Provide a synthetic last-frame for completeness; not used by playback.
    presenter._last_frame = QImage(8, 8, QImage.Format.Format_RGB888)
    presenter._last_frame.fill(0)
    return bridge, presenter


def _capture_motor_angle_emissions(bridge: VlaPanelBridge) -> list[tuple[int, int, float]]:
    emissions: list[tuple[int, int, float]] = []
    bridge.vla_motor_angle_deg.connect(
        lambda node, motor, deg: emissions.append((node, motor, deg))
    )
    return emissions


# ── Test class ───────────────────────────────────────────────────────────


class TestVlaActionPlayback(TestCaseFramework):
    """Acceptance tests for ``VlaPanelPresenter._handle_action_ready``."""

    @scenario(
        "action_chunk_emits_four_motor_gauge_signals",
        "An (8, 6) chunk produces exactly 4 vla_motor_angle_deg GUI emissions per step "
        "(all 6 positions are still written to the arm via write_goal; only joints 0-3 "
        "appear as motor angle gauges in the GUI)",
    )
    def test_action_chunk_emits_four_motor_gauge_signals(self, qtbot) -> None:
        bridge, presenter = _build_presenter()
        try:
            emissions = _capture_motor_angle_emissions(bridge)

            # All 6 joint positions in the chunk; write_goal() sends all 6 to the arm.
            # Only joints 0-3 (shoulder_pan … wrist_flex) emit vla_motor_angle_deg.
            chunk = np.full((8, 6), 7.5, dtype=np.float32)
            chunk[:, 4] = 99.0  # wrist_roll — goes to arm, excluded from GUI gauge
            chunk[:, 5] = 77.0  # gripper — handled via vla_gripper_state, not gauge

            presenter._handle_action_ready(chunk)
            qtbot.waitUntil(lambda: presenter._action_chunk is None, timeout=2000)

            assert len(emissions) == 8 * 4, (
                f"expected 32 GUI gauge emissions (8 steps × 4 displayed joints), "
                f"got {len(emissions)}"
            )
            for node, motor, _ in emissions:
                assert node == 0, f"unexpected node={node}; only node 0 is driven"
                assert motor in {0, 1, 2, 3}, f"unexpected motor={motor}"
            self.log(f"received {len(emissions)} motor-angle gauge emissions across 8 timesteps")
        finally:
            presenter.shutdown()

    @scenario(
        "wrist_roll_excluded_from_gauge_display",
        "wrist_roll (joint index 4) is excluded from the vla_motor_angle_deg GUI signal "
        "(write_goal() still forwards it to the physical arm)",
    )
    def test_wrist_roll_excluded_from_gauge_display(self, qtbot) -> None:
        bridge, presenter = _build_presenter()
        try:
            emissions = _capture_motor_angle_emissions(bridge)

            # Distinctive sentinel for wrist_roll; the other joints stay
            # at 0.0 so any emission carrying -42.0 is unambiguous proof
            # that wrist_roll leaked.
            chunk = np.zeros((4, 6), dtype=np.float32)
            chunk[:, 4] = -42.0

            presenter._handle_action_ready(chunk)
            qtbot.waitUntil(lambda: presenter._action_chunk is None, timeout=2000)

            for _, _, deg in emissions:
                assert deg != -42.0, (
                    f"wrist_roll sentinel value {deg} leaked into a motor emission"
                )
            self.log(f"verified no wrist_roll sentinel in {len(emissions)} emissions")
        finally:
            presenter.shutdown()

    @scenario(
        "gripper_held_open",
        "Gripper stays 'open' through varying gripper values and never emits motor signals",
    )
    def test_gripper_held_open(self, qtbot) -> None:
        bridge, presenter = _build_presenter()
        try:
            emissions = _capture_motor_angle_emissions(bridge)

            # Varying gripper values to ensure the held-open policy ignores them.
            chunk = np.zeros((4, 6), dtype=np.float32)
            chunk[:, 5] = np.array([25.0, 50.0, 75.0, 100.0], dtype=np.float32)

            states: list[str] = []
            bridge.vla_gripper_state_changed.connect(
                lambda: states.append(bridge.vla_gripper_state)
            )

            presenter._handle_action_ready(chunk)
            qtbot.waitUntil(lambda: presenter._action_chunk is None, timeout=2000)

            assert bridge.vla_gripper_state == "open", (
                f"gripper state must remain 'open'; got {bridge.vla_gripper_state!r}"
            )
            # gripper values from the chunk must not appear as motor angles.
            sentinel_values = {25.0, 50.0, 75.0, 100.0}
            for _, _, deg in emissions:
                assert deg not in sentinel_values, (
                    f"gripper value {deg} leaked into the motor signal stream"
                )
            self.log(f"gripper held 'open' across {chunk.shape[0]} timesteps")
        finally:
            presenter.shutdown()

    @scenario(
        "action_chunk_updates_motor_states",
        "presenter._motor_states reflects the final step of the chunk",
    )
    def test_action_chunk_updates_motor_states(self, qtbot) -> None:
        bridge, presenter = _build_presenter()
        try:
            final_step = np.array([12.5, -34.0, 56.0, -78.0, 0.0, 0.0], dtype=np.float32)
            chunk = np.zeros((8, 6), dtype=np.float32)
            chunk[-1] = final_step

            presenter._handle_action_ready(chunk)
            qtbot.waitUntil(lambda: presenter._action_chunk is None, timeout=2000)

            for motor_idx, expected in enumerate(final_step[:4]):
                stored = presenter._motor_states[0][motor_idx]["angle"]
                self.log(f"motor {motor_idx} final angle label = {stored!r}")
                assert f"{float(expected):.1f}" in stored, (
                    f"motor {motor_idx} angle {stored!r} does not reflect final step {expected}"
                )
        finally:
            presenter.shutdown()
