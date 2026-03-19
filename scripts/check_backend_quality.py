"""Backend quality baseline runner.

Usage:
  python scripts/check_backend_quality.py
  python scripts/check_backend_quality.py --skip-tests
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_step(name: str, command: list[str]) -> None:
    print(f"[QUALITY] {name}")
    print(f"[QUALITY] command: {' '.join(command)}")
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"[QUALITY] failed: {name}")
    print(f"[QUALITY] passed: {name}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run backend quality baseline checks")
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip pytest execution",
    )
    args = parser.parse_args()

    python = sys.executable

    run_step(
        "Python syntax compile",
        [python, "-m", "compileall", "-q", "app", "scripts", "tests"],
    )

    if not args.skip_tests:
        run_step(
            "Pytest suite",
            [python, "-m", "pytest", "-q"],
        )
    else:
        print("[QUALITY] skipped: Pytest suite\n")

    print("[QUALITY] backend baseline checks complete")


if __name__ == "__main__":
    main()
