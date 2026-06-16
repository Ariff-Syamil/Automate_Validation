"""Determinism and per-motor behaviour tests for the mock motor data source.

Two scenarios:

1. ``per_motor_golden_snapshot`` — proves the mock is deterministic. Each of
   M1..M4 must reproduce its committed 5-sample sequence exactly. Failure
   messages identify the specific motor and sample index that regressed.

2. ``per_motor_target_rpm_convergence`` — proves each motor is doing its own
   job. After 300 samples, each motor's mean RPM must sit close to its
   distinct ``_DEFAULT_TARGETS`` value (M1=1500, M2=1200, M3=900, M4=600).
   Catches a regression where two motors are accidentally aliased onto the
   same target, or where the convergence coefficient itself is broken.

Determinism caveat
------------------
Reproducibility holds within a CPython major version. The mock uses
``random.Random`` (Mersenne Twister) and standard float arithmetic, which are
stable for many years but are not formally guaranteed across major Python
upgrades. If a future Python upgrade changes these numerics, the golden
table must be regenerated in the same change.

Regenerating the golden table
-----------------------------
Run this module directly:

    python -m tests.test_suite_backend.testcase_mock_motor

It prints a ``_GOLDEN = { ... }`` block ready to paste back into this file.
"""

from __future__ import annotations

from itertools import islice
from unittest.mock import patch

import pytest

from backend.mock_motor_data import MAX_MOTORS, MOTOR_IDS, MockMotor, MotorBank, _DEFAULT_TARGETS
from tests.framework.base import TestCaseFramework, scenario


# Golden table — captured once from MotorBank(motor_ids=MOTOR_IDS, seed_base=1).
# Outer key is motor_id so a failing assertion points at the specific motor.
# Each row is (rpm, pos, ang, tor, tem, cur) for one sample. Field ``t`` is
# excluded intentionally — it is a wall-clock delta and not deterministic.
_GOLDEN: dict[str, list[tuple[float, float, float, float, float, float]]] = {
    "M1": [
        (73.5, 0.007, 44.1, 1.31, 25.0, 0.17),
        (143.9, 0.022, 130.5, 1.35, 25.0, 0.19),
        (212.3, 0.043, 257.8, 1.39, 25.0, 0.34),
        (274.8, 0.07,  62.7, 1.48, 25.0, 0.43),
        (337.1, 0.104, 265.0, 1.53, 25.0, 0.35),
    ],
    "M2": [
        (61.8, 0.006, 37.1,  1.49, 25.0, 0.17),
        (117.1, 0.018, 107.3, 1.59, 25.0, 0.22),
        (171.9, 0.035, 210.5, 1.6,  25.0, 0.19),
        (223.7, 0.057, 344.7, 1.57, 25.0, 0.31),
        (272.3, 0.085, 148.1, 1.61, 25.0, 0.34),
    ],
    "M3": [
        (44.0, 0.004, 26.4,  1.58, 25.0, 0.07),
        (87.2, 0.013, 78.7,  1.52, 25.0, 0.14),
        (125.9, 0.026, 154.2, 1.51, 25.0, 0.24),
        (163.5, 0.042, 252.3, 1.48, 25.0, 0.32),
        (201.7, 0.062, 13.3,  1.43, 25.0, 0.26),
    ],
    "M4": [
        (28.9, 0.003, 17.4,  1.41, 25.0, 0.0),
        (56.1, 0.009, 51.0,  1.34, 25.0, 0.0),
        (85.0, 0.017, 102.0, 1.3,  25.0, 0.17),
        (109.6, 0.028, 167.8, 1.17, 25.0, 0.15),
        (132.8, 0.041, 247.5, 1.09, 25.0, 0.1),
    ],
}


class TestMockMotorDeterminism(TestCaseFramework):
    """Two scenarios: determinism (golden snapshot) and per-motor behaviour."""

    # ── Scenario 1 ──
    @scenario(
        "per_motor_golden_snapshot",
        "Each of M1..M4 reproduces its committed 5-sample sequence",
    )
    def test_per_motor_golden_snapshot(self) -> None:
        self.log("test_per_motor_golden_snapshot: begin")
        bank = MotorBank(motor_ids=MOTOR_IDS, seed_base=1)

        captured: dict[str, list[tuple[float, ...]]] = {mid: [] for mid in MOTOR_IDS}
        n_samples = len(next(iter(_GOLDEN.values())))
        for _ in range(n_samples):
            for mid, s in bank.sample_all().items():
                captured[mid].append((s.rpm, s.pos, s.ang, s.tor, s.tem, s.cur))

        for mid in MOTOR_IDS:
            for i, (got, exp) in enumerate(zip(captured[mid], _GOLDEN[mid])):
                assert got == pytest.approx(exp, rel=1e-9, abs=1e-9), (
                    f"{mid} sample {i}: expected {exp}, got {got}"
                )
            self.log(f"  {mid}: {n_samples} samples match golden")

        self.log("test_per_motor_golden_snapshot: PASSED")

    # ── Scenario 2 ──
    @scenario(
        "per_motor_target_rpm_convergence",
        "Each motor converges toward its configured _DEFAULT_TARGETS RPM",
    )
    def test_per_motor_target_rpm_convergence(self) -> None:
        self.log("test_per_motor_target_rpm_convergence: begin")
        bank = MotorBank(motor_ids=MOTOR_IDS, seed_base=1)

        tail: dict[str, list[float]] = {mid: [] for mid in MOTOR_IDS}
        total_ticks = 300
        tail_from = 250
        for i in range(total_ticks):
            for mid, s in bank.sample_all().items():
                if i >= tail_from:
                    tail[mid].append(s.rpm)

        for mid in MOTOR_IDS:
            mean_rpm = sum(tail[mid]) / len(tail[mid])
            expected = _DEFAULT_TARGETS[mid]
            self.log(f"  {mid}: target={expected:.0f}  mean(last {len(tail[mid])})={mean_rpm:.1f}")
            assert abs(mean_rpm - expected) < 20.0, (
                f"{mid} did not converge: expected ~{expected}, "
                f"got mean {mean_rpm:.1f} over last {len(tail[mid])} samples"
            )

        self.log("test_per_motor_target_rpm_convergence: PASSED")

    @scenario("max_motors_guard", "MotorBank rejects more than MAX_MOTORS")
    def test_max_motors_guard(self) -> None:
        with pytest.raises(ValueError, match=f"Maximum {MAX_MOTORS} motors"):
            MotorBank(motor_ids=[f"M{i}" for i in range(MAX_MOTORS + 1)])

    @scenario("subset_motor_ids", "MotorBank supports deterministic motor subsets")
    def test_subset_motor_ids(self) -> None:
        bank = MotorBank(motor_ids=["M1", "M3"], seed_base=10)

        snapshot = bank.sample_all()

        assert bank.motor_ids == ["M1", "M3"]
        assert set(snapshot) == {"M1", "M3"}
        assert all(sample.motor_id in {"M1", "M3"} for sample in snapshot.values())

    @scenario("custom_target_rpm", "MockMotor converges toward a custom target RPM")
    def test_custom_target_rpm_convergence(self) -> None:
        motor = MockMotor("custom", seed=3, target_rpm=500.0)

        samples = [motor.sample().rpm for _ in range(300)]
        mean_tail = sum(samples[-50:]) / 50

        assert abs(mean_tail - 500.0) < 20.0

    @scenario("temperature_bounds", "Synthetic temperature remains in safe bounds")
    def test_temperature_bounds(self) -> None:
        motor = MockMotor("M1", seed=5, target_rpm=3000.0)

        temps = [motor.sample().tem for _ in range(1000)]

        assert min(temps) >= 25.0
        assert max(temps) <= 95.0

    @scenario("stream_shapes", "Mock motor stream helpers yield stable dictionaries")
    def test_stream_shapes(self) -> None:
        motor = MockMotor("M1", seed=1)
        bank = MotorBank(motor_ids=["M1", "M2"], seed_base=1)

        with patch("backend.mock_motor_data.time.sleep", return_value=None):
            one = next(motor.stream(interval=0.0))
            two = list(islice(bank.stream_all(interval=0.0), 2))

        assert set(one) == {"motor_id", "t", "rpm", "pos", "ang", "tor", "tem", "cur", "ready"}
        assert all(set(row) == {"M1", "M2"} for row in two)
        assert all(isinstance(sample["rpm"], float) for row in two for sample in row.values())


if __name__ == "__main__":
    bank = MotorBank(motor_ids=MOTOR_IDS, seed_base=1)
    rows: dict[str, list[tuple[float, ...]]] = {mid: [] for mid in MOTOR_IDS}
    for _ in range(5):
        for mid, s in bank.sample_all().items():
            rows[mid].append((s.rpm, s.pos, s.ang, s.tor, s.tem, s.cur))
    print("_GOLDEN = {")
    for mid in MOTOR_IDS:
        print(f'    "{mid}": [')
        for row in rows[mid]:
            print(f"        {row},")
        print("    ],")
    print("}")
