"""Restore curriculum source documents from a remote repository snapshot.

This pulls `storage/documents/*/orig.docx` from a reference repo and converts
them into stable raw filenames under `storage/raw/curriculum_standards/` so the
existing seed script can rebuild database records and Chroma chunks.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "storage" / "raw" / "curriculum_standards"
DEFAULT_REPO = "https://github.com/linics/CDAS-test2.git"

REMOTE_DOC_FILENAMES = {
    "1": "01_课程方案.docx",
    "2": "02_道德与法治.docx",
    "3": "03_语文.docx",
    "4": "04_历史.docx",
    "5": "05_英语.docx",
    "6": "06_地理.docx",
    "7": "07_科学.docx",
    "8": "08_物理.docx",
    "9": "09_生物学.docx",
    "10": "10_信息科技.docx",
    "11": "11_体育与健康.docx",
    "12": "12_艺术.docx",
    "13": "13_劳动.docx",
    "14": "14_数学.docx",
    "15": "15_化学.docx",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore raw curriculum documents from a remote repo")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="Git repository URL containing storage/documents")
    parser.add_argument(
        "--include-demo-lesson-plan",
        action="store_true",
        help="Also restore the extra lesson-plan test document as 16_校园垃圾分类教案.docx",
    )
    return parser.parse_args()


def clone_repo(repo_url: str, target: Path) -> None:
    subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(target)],
        check=True,
        cwd=ROOT,
    )


def restore_documents(repo_dir: Path, include_demo_lesson_plan: bool) -> list[Path]:
    source_root = repo_dir / "storage" / "documents"
    if not source_root.exists():
        raise RuntimeError(f"remote repository missing storage/documents: {repo_dir}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    restored: list[Path] = []

    for doc_id, filename in REMOTE_DOC_FILENAMES.items():
        source = source_root / doc_id / "orig.docx"
        if not source.exists():
            raise RuntimeError(f"missing expected source document: {source}")
        destination = RAW_DIR / filename
        shutil.copy2(source, destination)
        restored.append(destination)

    if include_demo_lesson_plan:
        extra_source = source_root / "16" / "orig.docx"
        if extra_source.exists():
            destination = RAW_DIR / "16_校园垃圾分类教案.docx"
            shutil.copy2(extra_source, destination)
            restored.append(destination)

    return restored


def main() -> None:
    args = parse_args()

    with tempfile.TemporaryDirectory(prefix="cdas-restore-") as tmp:
        repo_dir = Path(tmp) / "remote"
        print(f"[restore] cloning {args.repo}")
        clone_repo(args.repo, repo_dir)
        restored = restore_documents(repo_dir, args.include_demo_lesson_plan)

    print(f"[restore] restored {len(restored)} files into {RAW_DIR}")
    for path in restored:
        print(f"  - {path.name}")


if __name__ == "__main__":
    main()
