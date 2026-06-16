"""RobotArmController unit tests (mock-only, no hardware, no lerobot).

Covers the source-of-truth behaviour ported from holoscan-vla-work:

- test_disabled_controller_is_inert
- test_read_state_orders_by_joint_names
- test_write_goal_sync_writes_goal_position

The controller is exercised white-box by injecting a fake motor bus (the real
``connect()`` path requires lerobot, which is Linux-only and absent on the dev
machine). This isolates ``read_state`` / ``write_goal`` from the hardware setup.
"""

from __future__ import annotations

import numpy as np

from backend.robot_arm_controller import JOINT_NAMES, RobotArmController
from tests.framework.base import TestCaseFramework, scenario


class _FakeBus:
    """Minimal stand-in for a lerobot FeetechMotorsBus."""

    def __init__(self, present: dict[str, float]) -> None:
        self._present = present
        self.writes: list[tuple[str, dict[str, float]]] = []

    def sync_read(self, key: str) -> dict[str, float]:
        assert key == "Present_Position"
        return dict(self._present)

    def sync_write(self, key: str, goal: dict[str, float]) -> None:
        self.writes.append((key, dict(goal)))


def _connected_controller(present: dict[str, float]) -> tuple[RobotArmController, _FakeBus]:
    """Build a controller with a fake bus injected and marked connected."""
    arm = RobotArmController(enabled=False)
    bus = _FakeBus(present)
    arm._bus = bus
    arm._connected = True
    return arm, bus


class TestRobotArmController(TestCaseFramework):
    """Acceptance tests for ``backend.robot_arm_controller.RobotArmController``."""

    @scenario(
        "disabled_controller_is_inert",
        "A disabled controller never connects and its read/write methods are no-ops",
    )
    def test_disabled_controller_is_inert(self) -> None:
        arm = RobotArmController(enabled=False)
        assert arm.connect() is False
        assert arm.is_connected is False

        state = arm.read_state()
        assert state.shape == (6,)
        assert state.dtype == np.float32
        assert np.all(state == 0.0)

        # Must not raise even though no bus is attached.
        arm.write_goal(np.arange(6, dtype=np.float32))
        arm.disconnect()
        self.log("disabled controller stayed inert: zeros read, write no-op")

    @scenario(
        "read_state_orders_by_joint_names",
        "read_state returns Present_Position ordered by JOINT_NAMES as float32 (6,)",
    )
    def test_read_state_orders_by_joint_names(self) -> None:
        present = {name: float(i + 1) for i, name in enumerate(JOINT_NAMES)}
        arm, _bus = _connected_controller(present)

        state = arm.read_state()
        assert state.shape == (6,)
        assert state.dtype == np.float32
        expected = np.array([present[n] for n in JOINT_NAMES], dtype=np.float32)
        assert np.array_equal(state, expected)
        self.log(f"read_state ordered correctly: {state.tolist()}")

    @scenario(
        "write_goal_sync_writes_goal_position",
        "write_goal issues one sync_write('Goal_Position', {joint: value}) over all six joints",
    )
    def test_write_goal_sync_writes_goal_position(self) -> None:
        present = {name: 0.0 for name in JOINT_NAMES}
        arm, bus = _connected_controller(present)

        step = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0], dtype=np.float32)
        arm.write_goal(step)

        assert len(bus.writes) == 1, f"expected one sync_write, got {len(bus.writes)}"
        key, goal = bus.writes[0]
        assert key == "Goal_Position"
        assert set(goal.keys()) == set(JOINT_NAMES)
        for i, name in enumerate(JOINT_NAMES):
            assert goal[name] == float(step[i])
        self.log(f"write_goal wrote full 6-joint Goal_Position: {goal}")
