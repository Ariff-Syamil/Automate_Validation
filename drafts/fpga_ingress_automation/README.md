# FPGA Ingress Automation — DRAFT (pseudo-code, not wired in)

**Status: DRAFT. Nothing in this folder is real automation.**

This folder exists to track the *proposed* automation for the Ethernet
ingress-path robustness test cases:

- `TC-FPGA-010` — Ingress UDP Payload Size Sweep
- `TC-FPGA-011` — Back-to-Back Burst / Descriptor Ring Wraparound
- `TC-FPGA-012` — Wrong-Port UDP and Malformed Frame Rejection
- `TC-FPGA-013` — Reset-During-Transfer Recovery

(defined in `automate_5/holoscan_fpga/test_cases.yaml`)

It is deliberately kept **outside** `automation/` and `tests/` so that:

1. It is never picked up by pytest (`pytest.ini` sets `testpaths = tests`,
   so nothing here will accidentally run, "pass", or get recorded to
   `runs.yaml` as if it were real).
2. It's obvious at a glance this is a proposal, not shipped automation —
   you can track its progress toward the real `automation/fpga/` +
   `tests/test_suite_fpga/` implementation separately.
3. It won't be confused with `automation/gui/`, which is the only engine
   that currently produces genuine, tool-verified PASS/FAIL results.

## Why it's pseudo-code, not real code

Two pieces this automation depends on have never been confirmed against
real hardware:

1. **Stimulus** — how to actually address/format a UDP packet the real
   ingress-path firmware will accept. There are two conflicting candidates
   in the repo (see `stimulus.py`), and neither is confirmed.
2. **Readback** — how to read the real firmware/SGDMA state after a
   stimulus to decide pass/fail. Nothing implements this today for the
   ingress path; `readback.py` is a structural guess only.

Until both are confirmed, any pytest built on top of them would just be
guessing, not verifying. See `QUESTIONS.md` for the exact asks that unblock
this.

## File legend

Every non-obvious line in `stimulus.py` / `readback.py` /
`test_tc_fpga_ingress.py` is tagged inline:

- ✅ **GROUNDED** — copied from real, existing code/patterns in this repo
- ⚠️ **INFERRED** — a reasonable guess based on docs/patterns, unverified
- ❌ **PLACEHOLDER / UNKNOWN** — pure guesswork, will likely need to change

## Path to "real"

1. Get answers to `QUESTIONS.md` from Sheng Li / Seow Jie (or whoever owns
   the ingress-path firmware + Thor stimulus side).
2. Replace the ❌/⚠️ pieces in `stimulus.py` and `readback.py` with
   confirmed behavior.
3. Move/rename this folder's contents into `automation/fpga/` and
   `tests/test_suite_fpga/`, following the same structural pattern as
   `automation/gui/` + `tests/test_suite_gui/`.
4. Flip `automation_status` for `TC-FPGA-010`–`013` from `Not Ready` to
   `Ready` in `automate_5/holoscan_fpga/test_cases.yaml` only once step 3
   is done and a real run has produced a genuine PASS.
5. (Optional) Extend `automation/gui/executor.py`'s dispatch so these
   cases are triggerable the same way `TC-GUI-*` cases are today.
