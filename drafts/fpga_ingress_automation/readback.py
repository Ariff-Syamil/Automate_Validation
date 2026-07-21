"""DRAFT / PSEUDO-CODE — not wired into automation/ or tests/.

Read back firmware/SGDMA state after stimulus, for assertion.
See ../QUESTIONS.md for what needs to be confirmed before this is real.

STILL LARGELY UNGROUNDED FOR INGRESS. Nothing in the repo currently
implements this for the ingress path. Most functions below are still a
guess at *shape*, not fact.

⚠️ New evidence, 2026-07-20 (via Sheng Li, egress/SGDMA_TX only): manual
verification on the egress side does NOT appear to be UART-based. Sheng Li
described identification via `packet_type == "sgdma_tx"` + `dst_port ==
5000`, plus unspecified "other checking" in the SGDMA RTL (deferred to
Seow Jie), and shared one example of a decoded packet-capture JSON record
(see `EGRESS_REFERENCE_CAPTURE` below) that looks like the output of a
packet sniffer/decoder tool, not a UART log line. That tool was searched
for across every local checkout (automate_validation, Automate5, Board
Farm) and does NOT exist locally -- only the one example output has been
shared, not the tool itself (see QUESTIONS.md "Next steps").

This means the UART-based functions below (`read_uart_log`,
`parse_sgdma_capture`) may turn out to be the wrong channel entirely for
ingress verification, if ingress uses the same capture-based approach as
egress. Kept as-is (not deleted) until Seow Jie/Sheng Li confirm which
channel ingress actually uses -- see `parse_capture_record()` below for a
placeholder built against the egress JSON shape instead.
"""

from __future__ import annotations

import re

import serial  # GROUNDED dependency: used elsewhere (probe_pmod0_uart.py), different board/purpose

# GROUNDED (egress only, via Sheng Li, 2026-07-20): shape of one real
# decoded packet-capture record for SGDMA_TX. NOT confirmed this mechanism
# applies to ingress, and the tool that produced it hasn't been obtained.
EGRESS_REFERENCE_CAPTURE = {
    "direction": "tx",
    "ip": {"src": "192.168.0.101", "dst": "192.168.0.2"},
    "udp": {"dst_port": 5000},
    "packet_type": "sgdma_tx",
    "payload_length": 64,
    "fields": {"marker_le": "0xDEADBEEFCAFEF00D", "marker_repeats_cleanly": True},
}

# PLACEHOLDER -- real COM port for the Avant-X UART, unconfirmed (QUESTIONS.md #3, #4).
# May be moot if ingress verification turns out to be capture-based like egress.
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


def parse_capture_record(record: dict, *, expected_length: int) -> dict:
    """Alternative to UART: validate a decoded packet-capture record, matching
    the shape Sheng Li shared for egress (see EGRESS_REFERENCE_CAPTURE).

    NOT IMPLEMENTED / PLACEHOLDER. This assumes some capture/decode tool
    (not yet obtained -- see QUESTIONS.md "Next steps" #2) produces records
    shaped like EGRESS_REFERENCE_CAPTURE for the ingress direction too.
    Unconfirmed whether such a tool exists for RX, what it's called, or
    where it runs. Do not use until that tool (or its ingress-side
    equivalent) is actually in hand.
    """
    raise NotImplementedError(
        "Confirm whether an ingress-side equivalent of Sheng Li's egress "
        "packet-capture tool exists before implementing this"
    )


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
