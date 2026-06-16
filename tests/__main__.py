"""Allow `python -m tests` from the repository root."""

from tests.framework.runner import main

if __name__ == "__main__":
    raise SystemExit(main())
