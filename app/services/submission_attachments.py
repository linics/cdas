from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import (
    ParsingStatus,
    Submission,
    SubmissionAttachmentAnalysis,
    SubmissionAttachmentAsset,
)
from app.utils.storage import ensure_directory, remove_directory, save_upload_file
from app.utils.text_processing import UnsupportedDocumentError, parse_document

ALLOWED_ATTACHMENT_SUFFIXES = {".pdf", ".docx", ".txt"}
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024


class SubmissionAttachmentService:
    """处理学生附件上传、解析与存储。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.attachments_dir = self.settings.documents_dir.parent / "submission_attachments"
        ensure_directory(self.attachments_dir)

    @staticmethod
    def _storage_dir(asset: SubmissionAttachmentAsset) -> Path | None:
        return Path(asset.storage_path).parent if asset.storage_path else None

    @staticmethod
    async def _validate_upload(upload: UploadFile, filename: str) -> None:
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_ATTACHMENT_SUFFIXES:
            raise HTTPException(status_code=400, detail="仅支持上传 PDF、DOCX 或 TXT 附件")

        current_pos = upload.file.tell()
        upload.file.seek(0, 2)
        size_bytes = upload.file.tell()
        upload.file.seek(current_pos)
        await upload.seek(0)

        if size_bytes <= 0:
            raise HTTPException(status_code=400, detail="上传附件不能为空文件")
        if size_bytes > MAX_ATTACHMENT_BYTES:
            raise HTTPException(status_code=400, detail="上传附件不能超过 10MB")

    async def handle_upload(
        self,
        db: Session,
        submission: Submission,
        upload: UploadFile,
        uploader_id: int,
    ) -> SubmissionAttachmentAsset:
        filename = (upload.filename or "attachment").strip() or "attachment"
        await self._validate_upload(upload, filename)
        asset = SubmissionAttachmentAsset(
            submission_id=submission.id,
            uploader_id=uploader_id,
            original_filename=filename,
            storage_path="",
            mime_type=upload.content_type,
            source="upload",
            parsing_status=ParsingStatus.UPLOADED,
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)

        analysis = SubmissionAttachmentAnalysis(attachment_id=asset.id)
        db.add(analysis)
        db.commit()
        db.refresh(asset)

        suffix = Path(filename).suffix or ".bin"
        destination = self.attachments_dir / str(asset.id) / f"orig{suffix}"
        asset.storage_path = str(destination)
        asset.parsing_status = ParsingStatus.INDEXING
        db.commit()

        try:
            asset.size_bytes = await save_upload_file(upload, destination)
            raw_content = destination.read_bytes()
            pages = parse_document(raw_content, filename)
            extracted_text = "\n".join((page.get("text") or "").strip() for page in pages if (page.get("text") or "").strip()).strip()
            if not extracted_text:
                raise ValueError("附件内容为空，暂时无法分析")
            analysis.extracted_text = extracted_text
            analysis.summary_text = _summarize_text(extracted_text)
            analysis.error_msg = None
            analysis.analyzed_at = datetime.now(timezone.utc)
            asset.parsing_status = ParsingStatus.READY
        except UnsupportedDocumentError:
            if asset.size_bytes is None and destination.parent.exists():
                remove_directory(destination.parent)
            analysis.error_msg = "仅支持上传 PDF、DOCX 或 TXT 附件"
            analysis.analyzed_at = datetime.now(timezone.utc)
            asset.parsing_status = ParsingStatus.FAILED
        except Exception as exc:
            if asset.size_bytes is None and destination.parent.exists():
                remove_directory(destination.parent)
            analysis.error_msg = str(exc)
            analysis.analyzed_at = datetime.now(timezone.utc)
            asset.parsing_status = ParsingStatus.FAILED

        db.commit()
        db.refresh(asset)
        return asset

    def list_for_submission(self, db: Session, submission_id: int) -> list[SubmissionAttachmentAsset]:
        return (
            db.query(SubmissionAttachmentAsset)
            .filter(SubmissionAttachmentAsset.submission_id == submission_id)
            .order_by(SubmissionAttachmentAsset.created_at.asc())
            .all()
        )

    def get_for_submission(self, db: Session, submission_id: int, attachment_id: int) -> SubmissionAttachmentAsset | None:
        return (
            db.query(SubmissionAttachmentAsset)
            .filter(
                SubmissionAttachmentAsset.id == attachment_id,
                SubmissionAttachmentAsset.submission_id == submission_id,
            )
            .first()
        )

    def delete(self, db: Session, asset: SubmissionAttachmentAsset) -> None:
        storage_dir = self._storage_dir(asset)
        db.delete(asset)
        db.commit()
        if storage_dir:
            remove_directory(storage_dir)

    def delete_for_submission(self, db: Session, submission_id: int) -> None:
        assets = self.list_for_submission(db, submission_id)
        storage_dirs = {
            storage_dir
            for asset in assets
            if (storage_dir := self._storage_dir(asset)) is not None
        }
        for asset in assets:
            db.delete(asset)
        db.commit()
        for storage_dir in storage_dirs:
            remove_directory(storage_dir)


def _summarize_text(text: str, limit: int = 220) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"
