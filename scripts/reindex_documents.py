"""Rebuild Chroma index from existing document records."""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.db import SessionLocal
from app.models import Document, ParsingStatus
from app.services.inventory import InventoryService
from app.utils.text_processing import chunk_pages, parse_document


ROOT_DIR = Path(__file__).parent.parent


def resolve_file_path(file_path: str | None) -> Path | None:
    if not file_path:
        return None
    path = Path(file_path)
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def to_text_list(chunks: list[dict[str, Any]]) -> list[str]:
    texts: list[str] = []
    for chunk in chunks:
        value = chunk.get("text", "")
        texts.append(value if isinstance(value, str) else str(value))
    return texts


def reindex_documents() -> None:
    settings = get_settings()
    inventory = InventoryService(settings)

    with SessionLocal() as db:
        documents = db.query(Document).order_by(Document.id.asc()).all()
        print(f"Found {len(documents)} documents, rebuilding collection...")
        inventory._reset_collection()

        ready_count = 0
        failed_count = 0

        for document in documents:
            source_path = resolve_file_path(document.file_path)
            if source_path is None or not source_path.exists():
                document.parsing_status = ParsingStatus.FAILED
                document.error_msg = "file not found for reindex"
                db.commit()
                failed_count += 1
                print(f"[FAIL] id={document.id} missing file")
                continue

            try:
                document.parsing_status = ParsingStatus.INDEXING
                document.error_msg = None
                db.commit()

                raw_content = source_path.read_bytes()
                pages = parse_document(raw_content, document.filename or source_path.name)
                chunks = chunk_pages(document.id, pages, chunk_size=800, overlap=200)
                embeddings = inventory.embedding_provider.embed_texts(to_text_list(chunks))

                metadata = document.metadata_json if isinstance(document.metadata_json, dict) else {}
                subject_id_raw = metadata.get("subject_id")
                subject_name_raw = metadata.get("subject_name")
                subject_id = subject_id_raw if isinstance(subject_id_raw, int) else None
                subject_name = subject_name_raw if isinstance(subject_name_raw, str) and subject_name_raw else None

                if chunks:
                    normalized_chunks = [{**chunk, "document_id": document.id} for chunk in chunks]
                    inventory._upsert_chunks(normalized_chunks, embeddings, subject_id, subject_name)

                document.metadata_json = {
                    "page_count": len(pages),
                    "chunk_count": len(chunks),
                    "subject_id": subject_id,
                    "subject_name": subject_name,
                }
                document.parsing_status = ParsingStatus.READY
                document.error_msg = None
                db.commit()

                ready_count += 1
                print(f"[OK] id={document.id} chunks={len(chunks)}")
            except Exception as exc:
                document.parsing_status = ParsingStatus.FAILED
                document.error_msg = str(exc)
                db.commit()
                failed_count += 1
                print(f"[FAIL] id={document.id} {exc}")

        print(
            f"Reindex finished: total={len(documents)} ready={ready_count} failed={failed_count}"
        )


if __name__ == "__main__":
    reindex_documents()
