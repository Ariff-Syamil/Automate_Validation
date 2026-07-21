"""DRAFT / PSEUDO-CODE — not wired into automation/ or tests/.

Send UDP stimulus for TC-FPGA-010..013 (ingress-path robustness cases).
See ../QUESTIONS.md for what needs to be confirmed before this is real.

⚠️ PAYLOAD FORMAT IS STILL UNRESOLVED FOR INGRESS (see QUESTIONS.md #2).
As of 2026-07-20, Sheng Li confirmed the **egress** (SGDMA_TX) side sends a
plain raw payload with NO ECB wrapping -- a real captured egress packet
(FPGA 192.168.0.101 -> host 192.168.0.2, UDP dst port 5000) carried a
64-byte payload that was just the marker 0xDEADBEEFCAFEF00D (little-endian)
repeated 8x, with no ECB header/address/sequence fields at all. See
EGRESS_REFERENCE_CAPTURE below and QUESTIONS.md for the full packet.

This is evidence AGAINST option (a) below for at least the egress
direction. Seow Jie has not yet confirmed whether ingress framing mirrors
egress framing -- do not assume symmetry without confirmation. The two
candidates for INGRESS specifically remain:
  (a) ECB-wrapped, per automate5/packets/ecb_codec.py -> build_ecb_udp_payload()
      (2-byte Thor prefix + 6-byte ECB header + 4-byte address + payload,
       big-endian per struct.pack("!H"/"!I")). Weakened by the egress
       evidence above, but not ruled out for ingress specifically.
  (b) Raw payload (no wrapper), matching both the egress evidence above
      and the *set-aside* Board Farm script "thor_send_payload 1.py" (that
      script was set aside because it was never confirmed against real
      firmware behavior -- but its raw-payload shape now looks more
      plausible given the egress evidence).
This module still defaults to (a) pending Seow Jie's ingress-specific
confirmation, to avoid silently flipping an unconfirmed assumption. See
`build_marker_reference_payload()` below for a (b)-style builder, ready to
swap in once ingress framing is confirmed as raw.
"""

from __future__ import annotations

import socket
import struct
import time

from automate5.packets.ecb_codec import build_ecb_udp_payload  # GROUNDED: real module/function

# GROUNDED (egress only, via Sheng Li, 2026-07-20): one real decoded packet
# capture from SGDMA_TX. NOT confirmed for ingress -- kept here purely as a
# reference point, not consumed by the ingress functions below.
EGRESS_REFERENCE_CAPTURE = {
    "direction": "tx",
    "eth": {"dst_mac": "ca:fe:c0:ff:ee:00", "src_mac": "3c:6d:66:fa:2f:8f", "ethertype": "0x0800"},
    "ip": {"src": "192.168.0.101", "dst": "192.168.0.2", "protocol": 17, "ttl": 64},
    "udp": {"src_port": 42199, "dst_port": 5000, "length": 72},
    "packet_type": "sgdma_tx",
    "payload_length": 64,
    "fields": {"marker_le": "0xDEADBEEFCAFEF00D", "marker_repeats_cleanly": True},
}

# PLACEHOLDER -- confirm actual Avant-X IP and ingress UDP port (QUESTIONS.md #1).
# The egress reference capture above shows FPGA=192.168.0.101, host=192.168.0.2,
# port 5000 -- for SGDMA_TX (FPGA -> host). The INGRESS direction (host -> FPGA)
# this module targets is presumably the mirror (send TO 192.168.0.101), but
# that is an inference, not a confirmation. Port for ingress traffic is
# unconfirmed -- may or may not also be 5000.
TARGET_IP = "192.168.0.101"
TARGET_PORT = 5005

# PLACEHOLDER -- Sheng Li believes Thor reaches the FPGA over a 25G QSFP
# interface (QUESTIONS.md #7), but was explicitly unsure. socket.sendto()
# below does not bind to a specific interface; if Thor has multiple NICs,
# this may need an explicit bind to the 25G QSFP interface once confirmed.


def build_marker_reference_payload(size: int = 64) -> bytes:
    """Build a payload matching the egress reference capture's shape.

    GROUNDED shape (egress, via Sheng Li, 2026-07-20): the marker
    0xDEADBEEFCAFEF00D repeated to fill `size` bytes, little-endian, no
    wrapper. This mirrors what was actually observed on SGDMA_TX -- kept
    as a ready-to-use alternate builder for `build_payload()` below, in
    case Seow Jie confirms ingress uses the same raw/marker framing.
    NOT currently used by send_udp_payload()/build_payload() below until
    that confirmation lands.
    """
    marker = struct.pack("<Q", 0xDEADBEEFCAFEF00D)
    repeats = (size + len(marker) - 1) // len(marker)
    return (marker * repeats)[:size]


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
