from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH_MARKERS = (
    "app/contracts/",
    "app/api/v2/auth.py",
    "app/api/v2/assignments.py",
    "app/api/v2/submissions.py",
    "app/api/v2/evaluations.py",
    "app/config.py",
)
DOC_PATH_MARKERS = (
    "docs/PRODUCT_DESIGN.md",
    "docs/CONSTRAINT_GOVERNANCE.md",
    "frontend/docs/integration/api-contract-governance.md",
    "README.md",
)


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _inside_git_repo() -> bool:
    result = _run_git("rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"



def _changed_files() -> list[str]:
    base_sha = os.getenv("CDAS_CONTRACT_DOCS_BASE_SHA", "").strip()
    if base_sha:
        diff_args = ["diff", "--name-only", f"{base_sha}...HEAD"]
    else:
        head_parent = _run_git("rev-parse", "HEAD~1")
        if head_parent.returncode != 0:
            return []
        diff_args = ["diff", "--name-only", "HEAD~1", "HEAD"]

    result = _run_git(*diff_args)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]



def main() -> int:
    if not _inside_git_repo():
        print("[contract-docs-sync] skip: not inside a git repository")
        return 0

    changed_files = _changed_files()
    if not changed_files:
        print("[contract-docs-sync] skip: no diff base available")
        return 0

    contract_changed = any(path.startswith(CONTRACT_PATH_MARKERS) or path in CONTRACT_PATH_MARKERS for path in changed_files)
    if not contract_changed:
        print("[contract-docs-sync] pass: no contract files changed")
        return 0

    docs_changed = any(path.startswith(DOC_PATH_MARKERS) or path in DOC_PATH_MARKERS for path in changed_files)
    if docs_changed:
        print("[contract-docs-sync] pass: contract changes include doc updates")
        return 0

    print("[contract-docs-sync] fail: contract files changed without updating docs")
    print("Changed files:")
    for path in changed_files:
        print(f"  - {path}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
