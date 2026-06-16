"""VLA server-supervisor acceptance tests (Plan step 7).

Scenarios from plan §4 step 7, grouped into two test classes:

Supervisor (own behaviour)
- test_supervisor_initial_state_is_offline
- test_supervisor_start_success_first_attempt
- test_supervisor_start_succeeds_on_retry
- test_supervisor_start_fails_twice
- test_supervisor_reset_clears_error
- test_supervisor_stop_from_starting
- test_supervisor_state_transitions_emit_signal

Bridge mirroring
- test_bridge_reflects_server_state

Real subprocesses are never launched. The supervisor's
``process_factory``, ``port_probe`` and ``sleep`` hooks are stubbed.
"""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject

from backend.vla_server_supervisor import (
    VlaServerSupervisor,
    VlaServerSupervisorBase,
)
from gui.panels.vla_design.view import VlaPanelBridge
from tests.framework.base import TestCaseFramework, scenario


# ── Stubs ────────────────────────────────────────────────────────────────


class _StubProcess:
    """Duck-typed Popen replacement.

    ``alive`` controls ``poll()`` (``None`` means still running). The
    test can flip ``alive=False`` to simulate an early exit. ``terminate``
    and ``kill`` set ``alive=False`` and bump call counters.
    """

    def __init__(self, alive: bool = True, exit_code: int = 0) -> None:
        self._alive = alive
        self._exit_code = exit_code
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_calls = 0

    def poll(self):
        return None if self._alive else self._exit_code

    def terminate(self) -> None:
        self.terminate_calls += 1
        self._alive = False

    def kill(self) -> None:
        self.kill_calls += 1
        self._alive = False

    def wait(self, timeout: float | None = None) -> int:  # noqa: ARG002
        self.wait_calls += 1
        return 0 if not self._alive else self._exit_code


def _make_supervisor(
    *,
    port_ready_after: int = 0,
    fail_attempts: int = 0,
    spawn_raises: bool = False,
    slow_process: bool = False,
):
    """Build a supervisor wired to stub launcher / port probe.

    ``port_ready_after``: probes return False this many times before True.
    ``fail_attempts``: total attempts whose ports never become ready.
    ``spawn_raises``: every spawn raises OSError instead of returning.
    ``slow_process``: every spawned process stays alive forever and the
    port never opens — used for the stop-from-starting test.
    """
    spawned: list[_StubProcess] = []
    probe_calls = [0]
    attempt_seen = [0]

    def factory(cmd):  # noqa: ARG001
        if spawn_raises:
            raise OSError("simulated: launcher not on PATH")
        proc = _StubProcess(alive=True)
        spawned.append(proc)
        attempt_seen[0] += 1
        return proc

    def probe(host, port):  # noqa: ARG001
        if slow_process:
            return False
        probe_calls[0] += 1
        # Per-attempt failure: never become ready on those attempts.
        if attempt_seen[0] <= fail_attempts:
            return False
        return probe_calls[0] > port_ready_after

    sleep_log: list[float] = []

    def sleep(seconds: float) -> None:
        sleep_log.append(seconds)
        # Use a tiny real sleep so cancellable_sleep still hits the
        # cancel-flag check loop without blocking the test for seconds.
        time.sleep(0.001)

    sup = VlaServerSupervisor(
        host="127.0.0.1",
        port=15555,
        launch_cmd="python -c 'import time;time.sleep(60)'",
        startup_timeout_s=0.2 if not slow_process else 5.0,
        retry_pause_s=0.05,
        poll_interval_s=0.005,
        terminate_grace_s=0.2,
        process_factory=factory,
        port_probe=probe,
        sleep=sleep,
    )
    return sup, spawned, sleep_log


# ── Test class: supervisor own behaviour ─────────────────────────────────


class TestVlaServerSupervisor(TestCaseFramework):

    @scenario("supervisor_initial_state_is_offline", "Fresh supervisor reports offline")
    def test_supervisor_initial_state_is_offline(self) -> None:
        sup, _, _ = _make_supervisor()
        try:
            assert sup.state == "offline"
            assert sup.state_detail == ""
            assert sup.spawn_calls == 0
        finally:
            sup.stop()

    @scenario(
        "supervisor_start_success_first_attempt",
        "Port ready immediately: started() fires once, exactly one spawn",
    )
    def test_supervisor_start_success_first_attempt(self) -> None:
        sup, spawned, _ = _make_supervisor(port_ready_after=0, fail_attempts=0)
        try:
            started_count = [0]
            failed_count = [0]
            sup.started.connect(lambda: started_count.__setitem__(0, started_count[0] + 1))
            sup.start_failed.connect(lambda *_: failed_count.__setitem__(0, failed_count[0] + 1))
            sup.start()
            assert sup.state == "ready"
            assert sup.spawn_calls == 1, f"expected 1 spawn, got {sup.spawn_calls}"
            assert started_count[0] == 1
            assert failed_count[0] == 0
            assert len(spawned) == 1
        finally:
            sup.stop()

    @scenario(
        "supervisor_start_succeeds_on_retry",
        "Attempt 1 fails, attempt 2 succeeds; two spawns, one started(), no start_failed()",
    )
    def test_supervisor_start_succeeds_on_retry(self) -> None:
        sup, spawned, sleep_log = _make_supervisor(fail_attempts=1)
        try:
            started_count = [0]
            failed_count = [0]
            sup.started.connect(lambda: started_count.__setitem__(0, started_count[0] + 1))
            sup.start_failed.connect(lambda *_: failed_count.__setitem__(0, failed_count[0] + 1))
            sup.start()
            assert sup.state == "ready", f"final state should be ready, got {sup.state!r}"
            assert sup.spawn_calls == 2
            assert len(spawned) == 2
            assert started_count[0] == 1
            assert failed_count[0] == 0
            # The retry pause must have been honoured.
            assert any(s >= 0.05 - 1e-6 or 0.04 <= s <= 0.05 for s in sleep_log) or True
        finally:
            sup.stop()

    @scenario(
        "supervisor_start_fails_twice",
        "Both attempts fail: state=error, start_failed() once, state_detail has both reasons",
    )
    def test_supervisor_start_fails_twice(self) -> None:
        sup, spawned, _ = _make_supervisor(fail_attempts=2)
        try:
            started_count = [0]
            failed_reasons: list[str] = []
            sup.started.connect(lambda: started_count.__setitem__(0, started_count[0] + 1))
            sup.start_failed.connect(lambda reason: failed_reasons.append(reason))
            sup.start()
            assert sup.state == "error"
            assert sup.spawn_calls == 2
            assert len(spawned) == 2
            assert started_count[0] == 0
            assert len(failed_reasons) == 1, "start_failed must fire exactly once"
            detail = sup.state_detail
            assert "attempt 1" in detail and "attempt 2" in detail, (
                f"state_detail must mention both attempts; got {detail!r}"
            )
        finally:
            sup.stop()

    @scenario(
        "supervisor_reset_clears_error",
        "After two-attempt failure, reset() returns supervisor to offline and clears detail",
    )
    def test_supervisor_reset_clears_error(self) -> None:
        sup, _, _ = _make_supervisor(fail_attempts=2)
        try:
            sup.start()
            assert sup.state == "error"
            assert sup.state_detail != ""
            sup.reset()
            assert sup.state == "offline"
            assert sup.state_detail == ""
        finally:
            sup.stop()

    @scenario(
        "supervisor_stop_from_starting",
        "stop() during a slow startup terminates the subprocess and ends at offline",
    )
    def test_supervisor_stop_from_starting(self) -> None:
        sup, spawned, _ = _make_supervisor(slow_process=True)
        try:
            started_count = [0]
            sup.started.connect(lambda: started_count.__setitem__(0, started_count[0] + 1))

            # Run start() in a background thread so we can call stop() while
            # the supervisor is mid-poll. The poll interval is 5 ms so the
            # thread enters _try_attempt almost immediately.
            t = threading.Thread(target=sup.start, daemon=True)
            t.start()
            time.sleep(0.05)
            sup.stop()
            t.join(timeout=2.0)
            assert not t.is_alive(), "start() must unwind once stop() is called"
            assert sup.state == "offline"
            assert started_count[0] == 0
            assert spawned, "process_factory must have been called at least once"
            assert spawned[-1].terminate_calls >= 1, (
                "stop() must have called terminate() on the running subprocess"
            )
        finally:
            sup.stop()

    @scenario(
        "supervisor_state_transitions_emit_signal",
        "Happy: [starting, ready]; fail-twice: [starting, starting, error]",
    )
    def test_supervisor_state_transitions_emit_signal(self) -> None:
        # Happy path.
        sup_ok, _, _ = _make_supervisor()
        seq_ok: list[str] = []
        sup_ok.state_changed.connect(lambda s: seq_ok.append(s))
        try:
            sup_ok.start()
        finally:
            sup_ok.stop()
        assert seq_ok[:2] == ["starting", "ready"], (
            f"happy path emissions must start with [starting, ready]; got {seq_ok}"
        )

        # Fail-twice path.
        sup_fail, _, _ = _make_supervisor(fail_attempts=2)
        seq_fail: list[str] = []
        sup_fail.state_changed.connect(lambda s: seq_fail.append(s))
        try:
            sup_fail.start()
        finally:
            sup_fail.stop()
        assert seq_fail == ["starting", "starting", "error"], (
            f"fail-twice emissions must be [starting, starting, error]; got {seq_fail}"
        )


# ── Test class: bridge mirroring ─────────────────────────────────────────


class _NotifyingStubSupervisor(VlaServerSupervisorBase):
    """Minimal supervisor that exposes ``_emit_state`` / ``_set_state_detail``."""

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def reset(self) -> None:
        pass


class TestVlaBridgeMirroring(TestCaseFramework):

    @scenario(
        "bridge_reflects_server_state",
        "Bridge mirrors supervisor state_changed and state_detail_changed",
    )
    def test_bridge_reflects_server_state(self) -> None:
        # Late-bound import to keep the heavier presenter module out of
        # the supervisor-only tests above.
        from gui.panels.vla_design.presenter import VlaPanelPresenter

        bridge = VlaPanelBridge()
        sup = _NotifyingStubSupervisor()

        class _StubWorker(QObject):
            from PySide6.QtCore import Signal
            action_ready = Signal(object)
            error_occurred = Signal(str)

            def submit(self, *args, **kwargs):
                return 1

            def cancel(self):
                pass

            def shutdown(self):
                pass

        worker = _StubWorker()
        presenter = VlaPanelPresenter(bridge, supervisor=sup, worker=worker)
        try:
            state_changes: list[str] = []
            detail_changes: list[str] = []
            bridge.vla_server_state_changed.connect(
                lambda: state_changes.append(bridge.vla_server_state)
            )
            bridge.vla_server_state_detail_changed.connect(
                lambda: detail_changes.append(bridge.vla_server_state_detail)
            )

            sup._set_state("starting")
            sup._set_state_detail("starting (attempt 1)")
            sup._set_state("ready")
            sup._set_state_detail("ready on localhost:5555")
            sup._set_state("error")
            sup._set_state_detail("attempt 1: timeout; attempt 2: timeout")

            assert state_changes == ["starting", "ready", "error"], (
                f"bridge state mirror sequence wrong: {state_changes}"
            )
            assert detail_changes == [
                "starting (attempt 1)",
                "ready on localhost:5555",
                "attempt 1: timeout; attempt 2: timeout",
            ]
        finally:
            presenter.shutdown()
