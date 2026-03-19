"""Clean integration-test artifacts without wiping real data."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import or_

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import SessionLocal
from app.models import Assignment, Document, Evaluation, ProjectGroup, Submission, User


ROOT_DIR = Path(__file__).parent.parent
STORAGE_DIR = ROOT_DIR / "storage"
CHROMA_DIR = STORAGE_DIR / "chroma"
COLLECTION_NAME = "cdas-documents"

TEST_USER_RE = re.compile(r"^(teacher|student)_\d+_[a-z0-9]{4,8}$")
TEST_ASSIGNMENT_PREFIX = "Integration Assignment-"
TEST_DOCUMENT_RE = re.compile(r"^integration-\d+_[a-z0-9]{4,8}\.(txt|doc|docx|pdf)$", re.IGNORECASE)


@dataclass
class CleanupTargets:
    user_ids: list[int]
    assignment_ids: list[int]
    submission_ids: list[int]
    document_ids: list[int]
    document_paths: list[Path]


def _resolve_file_path(raw_path: str | None) -> Path | None:
    if not raw_path:
        return None
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def _is_test_user(user: User) -> bool:
    return bool(TEST_USER_RE.match(user.username or ""))


def _is_test_document(document: Document) -> bool:
    return bool(TEST_DOCUMENT_RE.match(document.filename or ""))


def collect_targets() -> CleanupTargets:
    with SessionLocal() as db:
        users = db.query(User).all()
        assignments = db.query(Assignment).all()
        documents = db.query(Document).all()

        test_users = [user for user in users if _is_test_user(user)]
        test_user_ids = {user.id for user in test_users}

        test_assignments = [
            assignment
            for assignment in assignments
            if (assignment.title or "").startswith(TEST_ASSIGNMENT_PREFIX) or assignment.created_by in test_user_ids
        ]
        test_assignment_ids = {assignment.id for assignment in test_assignments}

        submission_filters = []
        if test_assignment_ids:
            submission_filters.append(Submission.assignment_id.in_(test_assignment_ids))
        if test_user_ids:
            submission_filters.append(Submission.student_id.in_(test_user_ids))

        test_submissions: list[Submission] = []
        if submission_filters:
            test_submissions = db.query(Submission).filter(or_(*submission_filters)).all()
        test_submission_ids = {submission.id for submission in test_submissions}

        test_documents = [document for document in documents if _is_test_document(document)]
        test_document_ids = {document.id for document in test_documents}
        test_document_paths = [
            resolved
            for resolved in (_resolve_file_path(document.file_path) for document in test_documents)
            if resolved is not None
        ]

    return CleanupTargets(
        user_ids=sorted(test_user_ids),
        assignment_ids=sorted(test_assignment_ids),
        submission_ids=sorted(test_submission_ids),
        document_ids=sorted(test_document_ids),
        document_paths=test_document_paths,
    )


def _remove_document_dirs(paths: list[Path]) -> int:
    removed = 0
    for path in paths:
        folder = path.parent
        if not folder.exists():
            continue
        try:
            folder.relative_to(STORAGE_DIR / "documents")
        except ValueError:
            continue
        shutil.rmtree(folder, ignore_errors=True)
        removed += 1
    return removed


def _delete_vectors(document_ids: list[int]) -> str:
    if not document_ids:
        return "skip (no test documents)"

    try:
        from chromadb import PersistentClient
    except Exception as exc:
        return f"skip (chroma unavailable: {exc})"

    try:
        client = PersistentClient(path=str(CHROMA_DIR))
        collection = client.get_collection(COLLECTION_NAME)
    except Exception as exc:
        return f"skip (collection unavailable: {exc})"

    before = collection.count()
    try:
        collection.delete(where={"document_id": {"$in": document_ids}})  # type: ignore[arg-type]
    except Exception as exc:
        return f"failed ({exc})"
    after = collection.count()
    return f"ok (before={before}, after={after})"


def clean(dry_run: bool) -> None:
    targets = collect_targets()

    print("=" * 60)
    print("Selective cleanup for integration artifacts")
    print("=" * 60)
    print(f"test users: {len(targets.user_ids)}")
    print(f"test assignments: {len(targets.assignment_ids)}")
    print(f"test submissions: {len(targets.submission_ids)}")
    print(f"test documents: {len(targets.document_ids)}")

    if dry_run:
        print("dry-run enabled, no data changed")
        return

    with SessionLocal() as db:
        # Evaluations linked to target submissions or created by target users
        evaluation_filters = []
        if targets.submission_ids:
            evaluation_filters.append(Evaluation.submission_id.in_(targets.submission_ids))
        if targets.user_ids:
            evaluation_filters.append(Evaluation.evaluator_id.in_(targets.user_ids))
        if evaluation_filters:
            evaluations = db.query(Evaluation).filter(or_(*evaluation_filters)).all()
            for evaluation in evaluations:
                db.delete(evaluation)
            print(f"deleted evaluations: {len(evaluations)}")
        else:
            print("deleted evaluations: 0")

        # Submissions
        submission_filters = []
        if targets.assignment_ids:
            submission_filters.append(Submission.assignment_id.in_(targets.assignment_ids))
        if targets.user_ids:
            submission_filters.append(Submission.student_id.in_(targets.user_ids))
        if submission_filters:
            submissions = db.query(Submission).filter(or_(*submission_filters)).all()
            for submission in submissions:
                db.delete(submission)
            print(f"deleted submissions: {len(submissions)}")
        else:
            print("deleted submissions: 0")

        # Groups
        if targets.assignment_ids:
            groups = db.query(ProjectGroup).filter(ProjectGroup.assignment_id.in_(targets.assignment_ids)).all()
            for group in groups:
                db.delete(group)
            print(f"deleted groups: {len(groups)}")
        else:
            print("deleted groups: 0")

        # Assignments
        if targets.assignment_ids:
            assignments = db.query(Assignment).filter(Assignment.id.in_(targets.assignment_ids)).all()
            for assignment in assignments:
                db.delete(assignment)
            print(f"deleted assignments: {len(assignments)}")
        else:
            print("deleted assignments: 0")

        # Documents
        if targets.document_ids:
            documents = db.query(Document).filter(Document.id.in_(targets.document_ids)).all()
            for document in documents:
                db.delete(document)
            print(f"deleted documents: {len(documents)}")
        else:
            print("deleted documents: 0")

        # Users
        if targets.user_ids:
            users = db.query(User).filter(User.id.in_(targets.user_ids)).all()
            for user in users:
                db.delete(user)
            print(f"deleted users: {len(users)}")
        else:
            print("deleted users: 0")

        db.commit()

    removed_dirs = _remove_document_dirs(targets.document_paths)
    vector_result = _delete_vectors(targets.document_ids)
    print(f"removed document directories: {removed_dirs}")
    print(f"chroma vector cleanup: {vector_result}")
    print("cleanup completed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()
    clean(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
