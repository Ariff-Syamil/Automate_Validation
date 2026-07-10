"""DRAFT / PSEUDO-CODE — not wired into automation/ or tests/.

Read back firmware/SGDMA state after stimulus, for assertion.
See ../QUESTIONS.md for what needs to be confirmed before this is real.

ENTIRELY UNGROUNDED. Nothing in the repo currently implements this for
the ingress path. Every function below is a guess at *shape*, not fact.
"""

from __future__ import annotations

import re

import serial  # GROUNDED dependency: used elsewhere (probe_pmod0_uart.py), different board/purpose

# PLACEHOLDER -- real COM port for the Avant-X UART, unconfirmed (QUESTIONS.md #3, #4)
UART_PORT = "COM5"
UART_BAUD = 115200  # PLACEHOLDER -- unconfirmed (QUESTIONS.md #4)


def read_uart_log(timeout_s: float = 2.0) -> str:
    """Capture firmware UART output following a stimulus event."""
    # INFERRED pattern from probe_pmod0_uart.py's use of pyserial, but
    # that script probes a *different* board (CrossLink-NX) with no
    # expectation of specific firmware log content.
    with serial.Serial(UART_PORT, UART_BAUD, timeout=timeout_s) as ser:
        return ser.read(4096).decode(errors="replace")


def parse_sgdma_capture(log_text: str) -> dict:
    """Extract length/payload-hash fields the firmware is assumed to print.

    PLACEHOLDER regex. The actual firmware log format (field names,
    ordering, whether it prints a hash/CRC or raw hex) is unknown
    (QUESTIONS.md #4).
    """
    m = re.search(r"SGDMA_LEN=(\d+)\s+SGDMA_CRC=([0-9A-Fa-f]+)", log_text)
    if not m:
        raise ValueError("Expected SGDMA capture line not found in UART log")
    return {"length": int(m.group(1)), "crc": m.group(2).lower()}


def read_descriptor_ring_via_jtag() -> list[dict]:
    """Alternative to UART: read descriptor ring directly via JTAG/debug bridge.

    NOT IMPLEMENTED. Whether JTAG/debug-bridge memory read is even
    available/preferred over UART for this board is unknown
    (QUESTIONS.md #3).
    """
    raise NotImplementedError("Confirm JTAG/debug-bridge tooling before use")


def trigger_soft_reset() -> None:
    """TC-FPGA-013: assert/release a register-level reset, if one exists.

    NOT IMPLEMENTED. May not exist at all -- the only confirmed reset
    mechanism found so far is the Bellwin USB power splitter (full power
    cycle), which is slow and coarse-grained (QUESTIONS.md #6).
    """
    raise NotImplementedError("Confirm soft-reset mechanism before use")
