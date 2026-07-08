"""Consolidate Automate5 RuntimeLogger per-run log files into daily archives.

Automate5's ``RuntimeLogger`` (a module-level singleton created at import
time in the separate Automate5 checkout) writes a fresh
``logs/<YYMMDD>_<HHMMSS>.log`` / ``.jsonl`` pair for every process that
imports ``automate5.log`` -- every pytest run, every GUI launch, every
subprocess. Left alone this produces hundreds of near-empty files under
this repo's ``logs/`` directory.

This module merges those per-run files -- in chronological (filename) order
-- into per-day archives ``logs/<YYMMDD>.log`` / ``logs/<YYMMDD>.jsonl`` and
removes the originals. No log lines are discarded, only regrouped. This is
purely a validation-repo concern and does not touch the Automate5 source.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

# Per-run stems look like "260706_050712" (YYMMDD_HHMMSS). Archive files use
# the day-only stem "260706" so they are never re-picked-up as run files.
_RUN_STEM_RE = re.compile(r"^(\d{6})_(\d{6})$")
_RUN_SUFFIXES = (".log", ".jsonl")

# Skip files modified too recently, in case a still-running process
# (e.g. a live GUI session) is mid-write to them.
DEFAULT_MIN_AGE_SECONDS = 5.0


def consolidate_logs(log_dir: Path, *, min_age_seconds: float = DEFAULT_MIN_AGE_SECONDS) -> int:
    """Merge per-run log files in ``log_dir`` into daily archives.

    Args:
        log_dir: Directory containing RuntimeLogger's per-run ``.log`` /
            ``.jsonl`` files (typically ``<repo_root>/logs``).
        min_age_seconds: Files modified more recently than this are left
            alone, to avoid consolidating a file a live process is still
            writing to.

    Returns:
        The number of per-run files that were merged and removed.
    """
    if not log_dir.is_dir():
        return 0

    now = time.time()
    groups: dict[str, list[Path]] = {}
    for path in log_dir.iterdir():
        if not path.is_file() or path.suffix not in _RUN_SUFFIXES:
            continue
        match = _RUN_STEM_RE.match(path.stem)
        if not match:
            continue
        if now - path.stat().st_mtime < min_age_seconds:
            continue
        day = match.group(1)
        groups.setdefault(f"{day}{path.suffix}", []).append(path)

    consolidated = 0
    for archive_name, run_paths in groups.items():
        run_paths.sort(key=lambda p: p.name)
        archive_path = log_dir / archive_name
        with archive_path.open("a", encoding="utf-8") as out:
            for run_path in run_paths:
                text = run_path.read_text(encoding="utf-8")
                if text and not text.endswith("\n"):
                    text += "\n"
                out.write(text)
        for run_path in run_paths:
            run_path.unlink()
            consolidated += 1

    return consolidated
