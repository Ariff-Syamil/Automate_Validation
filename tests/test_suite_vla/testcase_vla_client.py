"""VlaClient acceptance tests (Plan step 2).

Pass criteria
─────────────
test_vla_client_mock_shape
    Constructing the client with ``mock=True`` and calling ``infer()`` with a
    dummy 224x224x3 uint8 frame yields a ``(T, 6)`` float32 action chunk.

test_vla_client_real_server_unreachable
    With ``mock=False`` and the underlying ``PolicyClient.get_action`` raising
    (server unreachable, dropped connection, etc.), ``infer()`` raises
    ``VlaClientError`` rather than hanging or letting the raw exception leak.

The reference protocol (``gr00t.policy.server_client.PolicyClient``,
``video.front``/``state.single_arm``/``state.gripper`` observation dict,
``single_arm``+``gripper`` action chunk concatenation) is taken from
``holoscan-vla-work/pipeline/linux_imx274_player.py::PolicyClientOp``.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from backend.vla_client import VlaClient, VlaClientError
from tests.framework.base import TestCaseFramework, scenario


_JOINT_NAMES = (
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
)


def _dummy_frame() -> np.ndarray:
    """Deterministic 224x224x3 uint8 RGB frame."""
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, size=(224, 224, 3), dtype=np.uint8)


def _zero_joint_state() -> np.ndarray:
    return np.zeros(6, dtype=np.float32)


class _UnreachableStubClient:
    """Stand-in for ``gr00t.policy.server_client.PolicyClient`` that simulates
    a server-side failure on every ``get_action`` call. Used to exercise the
    real-path error wrapper without requiring the GR00T runtime."""

    def __init__(self) -> None:
        self.calls = 0

    def get_action(self, obs):  # noqa: ARG002 — signature mirrors PolicyClient
        self.calls += 1
        raise ConnectionRefusedError("simulated: policy server unreachable")


class TestVlaClient(TestCaseFramework):
    """Unit-level acceptance tests for the VlaClient wrapper."""

    @scenario(
        "vla_client_mock_shape",
        "Mock mode returns a (T, 6) float32 chunk for a 224x224x3 uint8 frame",
    )
    def test_vla_client_mock_shape(self) -> None:
        horizon = 8
        client = VlaClient(
            host="localhost",
            port=5555,
            joint_names=_JOINT_NAMES,
            action_horizon=horizon,
            mock=True,
        )
        try:
            chunk = client.infer(
                prompt="pick up the red block",
                frame_rgb=_dummy_frame(),
                joint_state=_zero_joint_state(),
            )
        finally:
            client.close()

        self.log(f"mock chunk shape={chunk.shape} dtype={chunk.dtype}")
        assert isinstance(chunk, np.ndarray)
        assert chunk.shape == (horizon, 6), f"expected (T, 6), got {chunk.shape}"
        assert chunk.dtype == np.float32, f"expected float32, got {chunk.dtype}"
        assert np.isfinite(chunk).all(), "mock chunk must be finite"

    @scenario(
        "vla_client_real_server_unreachable",
        "Real-mode failures from PolicyClient.get_action raise VlaClientError",
    )
    def test_vla_client_real_server_unreachable(self) -> None:
        client = VlaClient(
            host="127.0.0.1",
            port=1,  # unused — stub is injected before any connect
            joint_names=_JOINT_NAMES,
            mock=False,
        )
        stub = _UnreachableStubClient()
        client._client = stub  # bypass _ensure_client so no gr00t import is needed

        self.log("injected stub PolicyClient that raises ConnectionRefusedError")
        t0 = time.monotonic()
        try:
            with pytest.raises(VlaClientError) as excinfo:
                client.infer(
                    prompt="ignored",
                    frame_rgb=_dummy_frame(),
                    joint_state=_zero_joint_state(),
                )
        finally:
            client.close()
        elapsed = time.monotonic() - t0

        self.log(f"infer() raised after {elapsed * 1000:.0f} ms: {excinfo.value}")
        assert stub.calls == 1, "stub.get_action must be invoked exactly once"
        assert "policy server" in str(excinfo.value).lower(), (
            "error message must identify the policy server as the failure point; "
            f"got: {excinfo.value!r}"
        )
        # Must not hang — a stub that raises immediately should return well
        # under a second even on slow CI hardware.
        assert elapsed < 2.0, (
            f"infer() blocked for {elapsed:.2f}s on a fast-raising stub; "
            "real-path wrapper must not hang on errors"
        )
