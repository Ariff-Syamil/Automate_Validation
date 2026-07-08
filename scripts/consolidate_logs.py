"""CLI to consolidate Automate5 RuntimeLogger per-run log files.

Merges ``logs/<YYMMDD>_<HHMMSS>.log`` / ``.jsonl`` files produced by
Automate5's RuntimeLogger into per-day archives (``logs/<YYMMDD>.log`` /
``.jsonl``), without losing any log lines. Safe to run anytime, including
right after closing the GUI or between test runs.

Usage:
    python scripts/consolidate_logs.py
    python scripts/consolidate_logs.py --log-dir path/to/logs
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

try:
    from automation.log_consolidation import DEFAULT_MIN_AGE_SECONDS, consolidate_logs
except ImportError:  # pragma: no cover - supports unusual direct import contexts
    sys.path.insert(0, str(REPO_ROOT))
    from automation.log_consolidation import DEFAULT_MIN_AGE_SECONDS, consolidate_logs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=REPO_ROOT / "logs",
        help="Directory containing RuntimeLogger's per-run log files (default: <repo_root>/logs).",
    )
    parser.add_argument(
        "--min-age-seconds",
        type=float,
        default=DEFAULT_MIN_AGE_SECONDS,
        help="Skip files modified more recently than this many seconds (default: %(default)s).",
    )
    args = parser.parse_args()

    count = consolidate_logs(args.log_dir, min_age_seconds=args.min_age_seconds)
    print(f"Consolidated {count} per-run log file(s) into daily archives under {args.log_dir}.")


if __name__ == "__main__":
    main()
