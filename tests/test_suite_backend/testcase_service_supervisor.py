"""Headless unit tests for ``ServiceSupervisor``.

The simulated workers in ``backend.services.simulated`` make these tests
deterministic and free of any hardware / network dependency. Each test
pumps the Qt event loop with ``app.processEvents()`` so cross-thread
queued signals are delivered before the assertions run.
"""

from __future__ import annotations

import sys
import time

from PySide6.QtCore import QElapsedTimer
from PySide6.QtWidgets import QApplication

from tests.framework.base import TestCaseFramework, scenario


def _pump(app: QApplication, ms: int) -> None:
    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < ms:
        app.processEvents()


def _wait_for(app: QApplication, predicate, timeout_ms: int) -> bool:
    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < timeout_ms:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


class TestServiceSupervisor(TestCaseFramework):
    """Lifecycle, dependency, and restart-policy coverage."""

    @scenario("supervisor_idle_initial", "Supervisor reports IDLE for every registered service before any start call")
    def test_initial_states_are_idle(self) -> None:
        from backend.services import (
            RestartPolicy,
            ServiceName,
            ServiceState,
            ServiceSupervisor,
        )
        from backend.services.simulated import (
            SimulatedCameraService,
            SimulatedGestureService,
            SimulatedVlaService,
        )

        app = QApplication.instance() or QApplication(sys.argv[:1])
        sup = ServiceSupervisor()
        sup.register(ServiceName.CAMERA, lambda: SimulatedCameraService(), policy=RestartPolicy.none())
        sup.register(ServiceName.VLA, lambda: SimulatedVlaService(), policy=RestartPolicy.none())
        sup.register(
            ServiceName.GESTURE,
            lambda: SimulatedGestureService(),
            policy=RestartPolicy.none(),
            requires=ServiceName.CAMERA,
        )

        for n in (ServiceName.CAMERA, ServiceName.VLA, ServiceName.GESTURE):
            assert sup.service_state(n) == ServiceState.IDLE

        snap = sup.snapshot()
        names = {row["name"] for row in snap}
        assert names == {"camera", "vla", "gesture"}
        assert all(row["state"] == "idle" for row in snap)

        sup.deleteLater()
        app.processEvents()

    @scenario("supervisor_start_stop", "Camera service transitions IDLE → RUNNING → IDLE")
    def test_camera_start_stop(self) -> None:
        from backend.services import (
            RestartPolicy,
            ServiceName,
            ServiceState,
            ServiceSupervisor,
        )
        from backend.services.simulated import SimulatedCameraService

        app = QApplication.instance() or QApplication(sys.argv[:1])
        sup = ServiceSupervisor()
        sup.register(ServiceName.CAMERA, lambda: SimulatedCameraService(), policy=RestartPolicy.none())

        assert sup.start_service(ServiceName.CAMERA)
        assert _wait_for(app, lambda: sup.service_state(ServiceName.CAMERA) == ServiceState.RUNNING, 5000)

        sup.stop_service(ServiceName.CAMERA)
        assert _wait_for(app, lambda: sup.service_state(ServiceName.CAMERA) == ServiceState.IDLE, 5000)

        sup.deleteLater()
        app.processEvents()

    @scenario("supervisor_dependency", "Starting gesture implicitly starts its camera dependency")
    def test_dependency_starts_parent(self) -> None:
        from backend.services import (
            RestartPolicy,
            ServiceName,
            ServiceState,
            ServiceSupervisor,
        )
        from backend.services.simulated import SimulatedCameraService, SimulatedGestureService

        app = QApplication.instance() or QApplication(sys.argv[:1])
        sup = ServiceSupervisor()
        sup.register(ServiceName.CAMERA, lambda: SimulatedCameraService(), policy=RestartPolicy.none())
        sup.register(
            ServiceName.GESTURE,
            lambda: SimulatedGestureService(),
            policy=RestartPolicy.none(),
            requires=ServiceName.CAMERA,
        )

        assert sup.start_service(ServiceName.GESTURE)
        assert _wait_for(app, lambda: sup.service_state(ServiceName.CAMERA) == ServiceState.RUNNING, 5000)
        assert _wait_for(app, lambda: sup.service_state(ServiceName.GESTURE) == ServiceState.RUNNING, 5000)

        # Stopping camera should also stop gesture (dependents-first).
        sup.stop_service(ServiceName.CAMERA)
        assert _wait_for(app, lambda: sup.service_state(ServiceName.GESTURE) == ServiceState.IDLE, 5000)
        assert _wait_for(app, lambda: sup.service_state(ServiceName.CAMERA) == ServiceState.IDLE, 5000)

        sup.deleteLater()
        app.processEvents()

    @scenario("supervisor_restart_policy", "VLA fault triggers bounded auto-restart")
    def test_restart_backoff(self) -> None:
        from backend.services import (
            RestartPolicy,
            ServiceName,
            ServiceState,
            ServiceSupervisor,
        )
        from backend.services.simulated import SimulatedVlaService

        app = QApplication.instance() or QApplication(sys.argv[:1])
        sup = ServiceSupervisor()
        # Three attempts at 0.1s spacing — keeps the test fast while still
        # exercising the backoff loop.
        sup.register(
            ServiceName.VLA,
            lambda: SimulatedVlaService(fault_after_iterations=3),
            policy=RestartPolicy.backoff([0.1, 0.1, 0.1]),
        )

        faults: list[tuple[str, int, str]] = []
        sup.service_fault.connect(lambda n, c, m: faults.append((n, c, m)))

        assert sup.start_service(ServiceName.VLA)
        # Run long enough for the worker to fault at least once.
        assert _wait_for(app, lambda: len(faults) >= 1, 5000)

        # Eventually the policy is exhausted and the service moves to FAULTED.
        assert _wait_for(app, lambda: sup.service_state(ServiceName.VLA) == ServiceState.FAULTED, 8000)

        sup.deleteLater()
        app.processEvents()
