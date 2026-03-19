"""Inventory Service：负责文件上传、解析、切片与向量入库。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional, Tuple, cast

try:
    from chromadb import PersistentClient
    from chromadb.errors import InvalidArgumentError
except Exception:  # pragma: no cover - optional runtime dependency on some CI hosts
    PersistentClient = None  # type: ignore[assignment]

    class InvalidArgumentError(Exception):
        pass
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Document, ParsingStatus, Subject
from app.services.ai import EmbeddingProvider, RerankProvider
from app.utils.storage import ensure_directory, remove_directory, save_upload_file
from app.utils.text_processing import chunk_pages, parse_document


COLLECTION_NAME = "cdas-documents"


class InventoryService:
    """封装文档上传与索引流程。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._chroma_client = None
        self.embedding_provider = EmbeddingProvider(settings)
        self.rerank_provider = RerankProvider(settings)
        ensure_directory(self.settings.documents_dir)
        ensure_directory(self.settings.chroma_persist_dir)

    @property
    def chroma_client(self):
        if self._chroma_client is None:
            if PersistentClient is None:
                raise RuntimeError(
                    "ChromaDB unavailable in current environment. "
                    "Install compatible sqlite/chromadb runtime first."
                )
            self._chroma_client = PersistentClient(path=str(self.settings.chroma_persist_dir))
        return self._chroma_client

    def get_collection(self):
        return self.chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    @staticmethod
    def _is_embedding_dimension_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return "dimension" in message and "embedding" in message

    def _reset_collection(self) -> None:
        try:
            self.chroma_client.delete_collection(name=COLLECTION_NAME)
        except Exception:
            pass

    def _upsert_chunks(
        self,
        chunks: list[dict],
        embeddings: list[list[float]],
        subject_id: Optional[int],
        subject_name: Optional[str],
    ) -> None:
        if not chunks:
            return

        ids = [chunk["id"] for chunk in chunks]
        metadatas = [
            {
                "document_id": chunk["document_id"],
                "page": chunk["page"],
                "chunk_id": chunk["id"],
                "order": chunk["order"],
                **({"subject_id": subject_id} if subject_id is not None else {}),
                **({"subject_name": subject_name} if subject_name else {}),
            }
            for chunk in chunks
        ]
        documents = [chunk["text"] for chunk in chunks]
        upsert_ids = cast(Any, ids)
        upsert_embeddings = cast(Any, embeddings)
        upsert_metadatas = cast(Any, metadatas)
        upsert_documents = cast(Any, documents)

        collection = self.get_collection()
        try:
            collection.upsert(  # type: ignore[arg-type]
                ids=upsert_ids,
                embeddings=upsert_embeddings,
                metadatas=upsert_metadatas,
                documents=upsert_documents,
            )
            return
        except Exception as exc:
            if not self._is_embedding_dimension_error(exc):
                raise
            print(
                "Chroma embedding dimension mismatch detected; "
                "recreating collection and retrying upsert."
            )

        self._reset_collection()
        collection = self.get_collection()
        collection.upsert(  # type: ignore[arg-type]
            ids=upsert_ids,
            embeddings=upsert_embeddings,
            metadatas=upsert_metadatas,
            documents=upsert_documents,
        )

    def _detect_subject_from_filename(
        self,
        db: Session,
        filename: str,
    ) -> Tuple[Optional[int], Optional[str]]:
        stem = Path(filename).stem
        candidate = stem.split("_", 1)[-1] if "_" in stem else stem
        subjects = db.query(Subject).all()
        for subject in subjects:
            if subject.name and subject.name in stem:
                return subject.id, subject.name
            if subject.name and subject.name == candidate:
                return subject.id, subject.name
        return None, None

    async def handle_upload(self, db: Session, upload: UploadFile) -> Document:
        """完整处理上传、解析、索引流程。"""

        document = Document(
            filename=upload.filename or "uploaded",
            parsing_status=ParsingStatus.UPLOADED,
            mime_type=upload.content_type,
            source="user",
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        suffix = Path(upload.filename or "").suffix or ".bin"
        document_dir = self.settings.documents_dir / str(document.id)
        destination = document_dir / f"orig{suffix}"
        size_bytes = await save_upload_file(upload, destination)

        document.file_path = str(destination)
        document.size_bytes = size_bytes
        document.parsing_status = ParsingStatus.INDEXING
        db.commit()

        try:
            subject_id, subject_name = self._detect_subject_from_filename(
                db, document.filename
            )
            raw_content = destination.read_bytes()
            pages = parse_document(raw_content, upload.filename or destination.name)
            chunks = chunk_pages(document.id, pages, chunk_size=800, overlap=200)
            texts: list[str] = []
            for chunk in chunks:
                text = chunk.get("text", "")
                texts.append(text if isinstance(text, str) else str(text))
            embeddings = self.embedding_provider.embed_texts(texts)

            if chunks:
                normalized_chunks = [
                    {
                        **chunk,
                        "document_id": document.id,
                    }
                    for chunk in chunks
                ]
                self._upsert_chunks(normalized_chunks, embeddings, subject_id, subject_name)

            document.metadata_json = {
                "page_count": len(pages),
                "chunk_count": len(chunks),
                "subject_id": subject_id,
                "subject_name": subject_name,
            }
            document.parsing_status = ParsingStatus.READY
        except Exception as exc: 
            document.parsing_status = ParsingStatus.FAILED
            document.error_msg = str(exc)
            # Log error for debugging
            print(f"Error processing document {document.id}: {exc}")
        finally:
            db.commit()
            db.refresh(document)
        
        return document

    def query_chunks(
        self,
        query: str,
        subject_ids: List[int] | None = None,
        document_ids: List[int] | None = None,
        limit: int = 12,
    ) -> list[dict]:
        if not query:
            return []
        embeddings = self.embedding_provider.embed_texts([query])
        if not embeddings:
            return []
        where: Any = None
        filters: List[dict[str, Any]] = []
        if subject_ids:
            filters.append({"subject_id": {"$in": subject_ids}})
        if document_ids:
            filters.append({"document_id": {"$in": document_ids}})
        if len(filters) == 1:
            where = filters[0]
        elif len(filters) > 1:
            where = {"$and": filters}
        collection = self.get_collection()
        try:
            result = collection.query(  # type: ignore[arg-type]
                query_embeddings=[embeddings[0]],
                n_results=limit,
                where=where,
                include=["metadatas", "documents"],
            )
        except InvalidArgumentError as exc:
            if self._is_embedding_dimension_error(exc):
                print(
                    "Chroma query skipped due to embedding dimension mismatch; "
                    "recreating collection."
                )
                self._reset_collection()
                return []
            print(f"Chroma query skipped due to embedding mismatch: {exc}")
            return []
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        chunks: list[dict] = []
        for idx, metadata in enumerate(metadatas):
            metadata = metadata or {}
            text = documents[idx] if idx < len(documents) else ""
            chunks.append(
                {
                    "id": metadata.get("chunk_id") or f"chunk_{idx}",
                    "page": metadata.get("page"),
                    "order": metadata.get("order"),
                    "text": text,
                    "document_id": metadata.get("document_id"),
                    "subject_id": metadata.get("subject_id"),
                    "subject_name": metadata.get("subject_name"),
                }
            )
        if not chunks:
            return []
        reranked = self.rerank_provider.rerank(query, [c["text"] for c in chunks])
        if not reranked:
            return chunks
        return [chunks[i] for i in reranked if 0 <= i < len(chunks)]

    def list_documents(self, db: Session) -> list[Document]:
        return db.query(Document).order_by(Document.upload_date.desc()).all()

    def get_document(self, db: Session, document_id: int) -> Document | None:
        return db.get(Document, document_id)

    def delete_document(self, db: Session, document: Document) -> None:
        """删除 SQL 记录、文件目录与向量条目。"""

        collection = self.get_collection()
        collection.delete(where={"document_id": document.id})

        if document.file_path:
            doc_dir = Path(document.file_path).parent
            remove_directory(doc_dir)

        db.delete(document)
        db.commit()
