"""DRAFT / PSEUDO-CODE — not wired into automation/ or tests/.

Send UDP stimulus for TC-FPGA-010..013 (ingress-path robustness cases).
See ../QUESTIONS.md for what needs to be confirmed before this is real.

⚠️ PAYLOAD FORMAT IS UNRESOLVED (see QUESTIONS.md #2). Two candidates exist
in the repo and they disagree:
  (a) ECB-wrapped, per automate5/packets/ecb_codec.py -> build_ecb_udp_payload()
      (2-byte Thor prefix + 6-byte ECB header + 4-byte address + payload,
       big-endian per struct.pack("!H"/"!I")).
  (b) Raw little-endian numpy bytes, per the *set-aside* Board Farm script
      "thor_send_payload 1.py" (not used here because it was never
      confirmed against real firmware behavior).
This module defaults to (a) because it's the only reviewed, structured
module in the actual codebase -- but it is NOT confirmed to be what the
ingress-path firmware for TC-FPGA-010..013 actually expects on the wire.
"""

from __future__ import annotations

import socket
import time

from automate5.packets.ecb_codec import build_ecb_udp_payload  # GROUNDED: real module/function

# PLACEHOLDER -- confirm actual Avant-X IP and ingress UDP port (QUESTIONS.md #1)
TARGET_IP = "192.168.1.50"
TARGET_PORT = 5005


def send_udp_payload(payload: bytes, *, dest_port: int = TARGET_PORT) -> None:
    """Send one UDP datagram to the FPGA ingress path."""
    # INFERRED: assumes a plain socket.sendto is sufficient (no ARP/link
    # setup needed, no THOR/holoscan operator graph required). The
    # set-aside thor_send_payload script used holoscan operators instead
    # of raw sockets -- unclear if that's required on this NIC/driver.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(payload, (TARGET_IP, dest_port))


def build_payload(size: int, *, seed: int = 0) -> bytes:
    """Build a deterministic payload of `size` bytes for byte-exact readback checks."""
    # INFERRED framing choice; see module docstring above (QUESTIONS.md #2).
    body = bytes((seed + i) % 256 for i in range(size))
    return build_ecb_udp_payload(payload=body)  # GROUNDED: real signature from ecb_codec.py


def send_burst(payload: bytes, count: int, *, inter_frame_gap_s: float = 0.0) -> None:
    """TC-FPGA-011: send `count` back-to-back frames."""
    for _ in range(count):
        send_udp_payload(payload)
        if inter_frame_gap_s:
            time.sleep(inter_frame_gap_s)  # PLACEHOLDER: real min inter-frame-gap unknown


def send_wrong_port(payload: bytes) -> None:
    """TC-FPGA-012: send to a port the firmware should reject."""
    # PLACEHOLDER -- "wrong port" needs to be a port the FSM actually
    # filters on. Unknown until the UDP/IP header filter logic is
    # confirmed (QUESTIONS.md #1, #5).
    send_udp_payload(payload, dest_port=TARGET_PORT + 1)


def send_malformed_frame() -> None:
    """TC-FPGA-012: send a short/runt or bad-checksum frame.

    NOT IMPLEMENTED. Building a deliberately malformed frame (wrong
    checksum, truncated length) typically requires a raw socket
    (SOCK_RAW) or scapy, bypassing the normal UDP stack -- unconfirmed
    whether that's available/permitted on the Thor host used for testing.
    """
    raise NotImplementedError("Confirm malformed-frame injection method before use")
