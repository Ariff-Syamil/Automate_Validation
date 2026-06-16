"""VlaInferenceWorker acceptance tests (Plan step 3).

Pass criteria
─────────────
test_worker_emits_action_ready
    A worker constructed with a stub ``VlaClient`` that returns a fixed
    ``(T, 6)`` array must, after a single ``submit()``, emit
    ``action_ready`` exactly once with that array, on the GUI thread.

test_worker_emits_error_on_failure
    A worker constructed with a stub ``VlaClient`` whose ``infer()`` raises
    ``VlaClientError`` must, after a single ``submit()``, emit
    ``error_occurred`` exactly once with the failure message and must not
    emit ``action_ready``.

Both tests run on the suite-wide ``QApplication`` provided by
``conftest.qapp_gui`` and use ``pytest-qt``'s ``qtbot`` to wait for the
signal under a strict timeout.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.vla_client import VlaClientError
from backend.vla_worker import VlaInferenceWorker
from tests.framework.base import TestCaseFramework, scenario


_JOB_TIMEOUT_MS = 2000


def _dummy_frame() -> np.ndarray:
    return np.zeros((224, 224, 3), dtype=np.uint8)


def _dummy_joint_state() -> np.ndarray:
    return np.zeros(6, dtype=np.float32)


class _StubClient:
    """Synchronous stub matching ``VlaClient`` 's ``infer()`` surface."""

    def __init__(
        self,
        chunk: np.ndarray | None = None,
        exc: Exception | None = None,
    ) -> None:
        self._chunk = chunk
        self._exc = exc
        self.calls = 0

    def infer(self, prompt, frame_rgb, joint_state):  # noqa: ARG002
        self.calls += 1
        if self._exc is not None:
            raise self._exc
        return self._chunk

    def close(self) -> None:
        pass


class TestVlaInferenceWorker(TestCaseFramework):
    """Threaded acceptance tests for the VLA inference worker."""

    @scenario(
        "worker_emits_action_ready",
        "Worker emits action_ready with the (T, 6) chunk returned by the client",
    )
    def test_worker_emits_action_ready(self, qtbot) -> None:
        expected = np.full((8, 6), 1.5, dtype=np.float32)
        stub = _StubClient(chunk=expected)
        worker = VlaInferenceWorker(stub)

        actions: list[np.ndarray] = []
        errors: list[str] = []
        worker.action_ready.connect(lambda c: actions.append(c))
        worker.error_occurred.connect(lambda e: errors.append(e))

        self.log("submitting one job to the worker")
        try:
            with qtbot.waitSignal(worker.action_ready, timeout=_JOB_TIMEOUT_MS):
                worker.submit("pick up the red block", _dummy_frame(), _dummy_joint_state())
        finally:
            worker.shutdown()

        assert stub.calls == 1, f"expected 1 infer call, got {stub.calls}"
        assert len(actions) == 1, f"expected 1 action_ready emission, got {len(actions)}"
        chunk = actions[0]
        self.log(f"received chunk shape={chunk.shape} dtype={chunk.dtype}")
        assert isinstance(chunk, np.ndarray)
        assert chunk.shape == (8, 6)
        assert chunk.dtype == np.float32
        assert np.array_equal(chunk, expected)
        assert errors == [], f"unexpected error emissions: {errors}"

    @scenario(
        "worker_emits_error_on_failure",
        "Worker emits error_occurred and not action_ready when infer() raises",
    )
    def test_worker_emits_error_on_failure(self, qtbot) -> None:
        stub = _StubClient(exc=VlaClientError("simulated policy server failure"))
        worker = VlaInferenceWorker(stub)

        actions: list[np.ndarray] = []
        errors: list[str] = []
        worker.action_ready.connect(lambda c: actions.append(c))
        worker.error_occurred.connect(lambda e: errors.append(e))

        self.log("submitting one job to the worker with a raising client")
        try:
            with qtbot.waitSignal(worker.error_occurred, timeout=_JOB_TIMEOUT_MS) as blocker:
                worker.submit("ignored", _dummy_frame(), _dummy_joint_state())
        finally:
            worker.shutdown()

        assert blocker.signal_triggered, "error_occurred did not fire"
        assert stub.calls == 1
        assert len(errors) == 1, f"expected 1 error emission, got {len(errors)}"
        self.log(f"received error: {errors[0]}")
        assert "simulated policy server failure" in errors[0]
        assert actions == [], f"action_ready must not fire on failure; got {actions}"
