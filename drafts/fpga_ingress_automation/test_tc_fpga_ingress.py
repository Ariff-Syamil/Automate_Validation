"""DRAFT / PSEUDO-CODE — not wired into automation/ or tests/.

Pytest wrapper for TC-FPGA-010..013 -- combines stimulus + readback +
assertion. Intentionally kept outside tests/ so pytest.ini's
`testpaths = tests` never collects it; do not move this into tests/
until stimulus.py and readback.py have been de-guessed per QUESTIONS.md.

GROUNDED pattern: the automation_status/automation_readiness gate and the
append_run() call are copied directly from automation/gui/executor.py and
automation/gui/run_store.py, both of which ARE generic/reusable as-is.

Everything else (payload format, target port, log parsing) inherits the
uncertainty from stimulus.py / readback.py.
"""

from __future__ import annotations

import pytest

from drafts.fpga_ingress_automation import stimulus, readback

# GROUNDED: automation.gui.run_store.append_run is version/test-case
# generic, not GUI-specific -- a real FPGA runner could reuse it as-is.
from automation.gui.run_store import append_run

VERSION = "automate_5"


@pytest.mark.parametrize("size", [1, 63, 64, 65, 512, 1500])  # INFERRED tkeep/MTU boundaries
def test_tc_fpga_010_payload_sweep(size):
    payload = stimulus.build_payload(size)
    stimulus.send_udp_payload(payload)

    log = readback.read_uart_log()
    captured = readback.parse_sgdma_capture(log)  # will raise until log format is real

    assert captured["length"] == size, (
        f"expected {size} bytes, firmware reported {captured['length']}"
    )
    # PLACEHOLDER: comparing a CRC/hash string assumes firmware computes
    # and prints one; might instead need a full byte-for-byte memory dump.


@pytest.mark.parametrize("count", [1, 8, 33])  # INFERRED: 33 assumes a 32-deep descriptor ring
def test_tc_fpga_011_burst_wraparound(count):
    payload = stimulus.build_payload(64)
    stimulus.send_burst(payload, count)

    log = readback.read_uart_log()
    # PLACEHOLDER: assumes one capture line per frame in the burst; real
    # firmware log format for multi-frame bursts is unconfirmed.
    captures = [readback.parse_sgdma_capture(line) for line in log.splitlines() if line]
    assert len(captures) == count, f"expected {count} frames captured, got {len(captures)}"


def test_tc_fpga_012_wrong_port_no_hang():
    baseline = stimulus.build_payload(64)

    stimulus.send_udp_payload(baseline)
    assert readback.parse_sgdma_capture(readback.read_uart_log())["length"] == 64

    stimulus.send_wrong_port(baseline)
    log_after_wrong_port = readback.read_uart_log()
    # PLACEHOLDER: assumes absence of a capture line means "correctly
    # dropped" -- real criterion (e.g. an explicit drop counter) unknown.
    with pytest.raises(ValueError):
        readback.parse_sgdma_capture(log_after_wrong_port)

    stimulus.send_udp_payload(baseline)
    assert readback.parse_sgdma_capture(readback.read_uart_log())["length"] == 64, (
        "FSM did not recover after wrong-port packet"
    )


def test_tc_fpga_013_reset_during_transfer():
    # NOT IMPLEMENTED: readback.trigger_soft_reset() raises until a real
    # reset mechanism is confirmed. Bellwin power-cycle is the only known
    # fallback today, which this pseudo-code does not attempt to drive.
    readback.trigger_soft_reset()

    payload = stimulus.build_payload(64)
    stimulus.send_udp_payload(payload)
    assert readback.parse_sgdma_capture(readback.read_uart_log())["length"] == 64


def _record_and_assert(test_case_id: str, passed: bool, notes: str) -> None:
    """Optional: write a real run record instead of a human ticking a GUI box."""
    append_run(VERSION, test_case_id, "PASS" if passed else "FAIL", notes=notes)
    assert passed, notes
