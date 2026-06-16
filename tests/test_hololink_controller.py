"""Negative-path tests for HololinkCameraController.

Two complementary test strategies:

1. test_configure_no_hardware_emits_error  (Test 1)
     - Uses a deliberately-unreachable IP (192.168.99.99).
     - Always runs regardless of whether real hardware is connected.
     - Hardware-independent — safe for CI / regression.
     - Uses qtbot.waitSignal (push pattern).

2. test_configure_real_ip_unplugged  (Test 2)
     - Uses the production IP (192.168.0.2) — the same default the GUI ships with.
     - Auto-skipped when a board IS reachable at that IP (probe at collection time).
     - Only runs when the cable is actually unplugged or the board is off.
     - Uses pull-style polling on last_error / is_live() — no Qt event loop required.

Run with:
    pytest -s -v tests/test_hololink_controller.py

Requirements: pytest-qt (already in [dependency-groups] test in pyproject.toml).
"""

from __future__ import annotations

import time

import pytest

from backend.hololink_camera_controller import HololinkCameraController


_FAKE_IP = "192.168.99.99"  # guaranteed not on the local subnet
_REAL_IP = "192.168.0.2"    # production Hololink board IP


def _hololink_reachable(ip: str = _REAL_IP, timeout_s: float = 1.5) -> bool:
    """Probe: True if a Hololink board is broadcasting at `ip` right now.

    Used by the skipif on test_configure_real_ip_unplugged so that the test
    auto-skips when real hardware is plugged in.  Any exception → unreachable.
    """
    try:
        import hololink as hololink_module  # noqa: PLC0415
    except ImportError:
        return False
    try:
        hololink_module.Enumerator.find_channel(
            channel_ip=ip,
            timeout=hololink_module.Timeout(timeout_s),
        )
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Test 1 — fake IP, always runs, signal-wait (qtbot) pattern
# ---------------------------------------------------------------------------

@pytest.mark.timeout(20)
def test_configure_no_hardware_emits_error(qtbot):
    """When configure targets an unreachable IP, configure_error fires within
    ~10 s and last_error is populated; the pipeline is not live.

    This test always runs regardless of whether real hardware is connected
    because 192.168.99.99 is guaranteed not to be on the local subnet.
    """
    controller = HololinkCameraController()
    cfg = {"ip": _FAKE_IP, "mode": 1}

    with qtbot.waitSignal(controller.configure_error, timeout=15_000) as blocker:
        controller.apply_preview(
            cam_mode=0,
            sensor_idx_slot0=0,
            sensor_idx_slot1=1,
            hololink_cfg=cfg,
        )

    assert _FAKE_IP in blocker.args[0], f"IP missing from error message: {blocker.args[0]}"
    assert "No Hololink board responding" in blocker.args[0]
    assert controller.last_error == blocker.args[0]
    assert not controller.is_live()


# ---------------------------------------------------------------------------
# Test 2 — real IP, only when board is truly unplugged, pull-state pattern
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    _hololink_reachable(),
    reason=(
        f"Test requires the Hololink board at {_REAL_IP} to be UNPLUGGED or "
        "powered off.  Skipping because a board is currently announcing on the network."
    ),
)
@pytest.mark.timeout(20)
def test_configure_real_ip_unplugged():
    """Unplug-the-cable scenario against the production IP (192.168.0.2).

    Verifies that the same timeout-and-error path works with the exact
    configuration the GUI ships with.

    Uses pull-style polling on last_error / is_live() — no qtbot needed.
    This demonstrates how scripts or test frameworks without a running Qt
    event loop can deterministically observe configure failures.
    """
    controller = HololinkCameraController()
    cfg = {"ip": _REAL_IP, "mode": 0}

    controller.apply_preview(
        cam_mode=0,
        sensor_idx_slot0=0,
        sensor_idx_slot1=1,
        hololink_cfg=cfg,
    )

    deadline = time.time() + 15.0
    while time.time() < deadline and controller.last_error is None and not controller.is_live():
        time.sleep(0.1)

    assert controller.last_error is not None, "Expected configure_error but got none after 15 s"
    assert _REAL_IP in controller.last_error, f"IP missing from error: {controller.last_error}"
    assert "No Hololink board responding" in controller.last_error
    assert not controller.is_live()
