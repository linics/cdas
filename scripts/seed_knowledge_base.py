"""批量导入 raw/ 目录下的文档到 RAG 知识库。

此脚本直接操作 InventoryService 内部逻辑，绕过 FastAPI UploadFile。
"""
import asyncio
import sys
from pathlib import Path
from typing import Any, cast

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import SessionLocal
from app.config import get_settings
from app.models import Document, ParsingStatus, Subject
from app.services.ai import EmbeddingProvider
from app.utils.text_processing import chunk_pages, parse_document
from chromadb import PersistentClient

RAW_DIR = Path(__file__).parent.parent / "storage" / "raw" / "curriculum_standards"
STORAGE_DIR = Path(__file__).parent.parent / "storage"

stdout_handle = cast(Any, sys.stdout)
if hasattr(stdout_handle, "reconfigure"):
    stdout_handle.reconfigure(encoding="utf-8", errors="replace")


def get_chroma_collection():
    client = PersistentClient(path=str(STORAGE_DIR / "chroma"))
    return client.get_or_create_collection(
        name="cdas-documents",
        metadata={"hnsw:space": "cosine"},
    )


def seed():
    print("=" * 50)
    print("批量导入 RAG 知识库")
    print("=" * 50)
    
    settings = get_settings()
    embedding_provider = EmbeddingProvider(settings)
    collection = get_chroma_collection()
    
    files = sorted(RAW_DIR.glob("*.docx"))
    
    if not files:
        print(f"未找到文件！请检查目录: {RAW_DIR}")
        return
    
    print(f"\n发现 {len(files)} 个文档待导入\n")
    
    success = 0
    failed = 0
    
    for i, filepath in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {filepath.name}...", end=" ")
        
        try:
            with SessionLocal() as db:
                existing_doc = db.query(Document).filter(Document.filename == filepath.name).first()
                if existing_doc:
                    if existing_doc.source != "system":
                        existing_doc.source = "system"
                        db.commit()
                    print(f"[SKIP] already imported (ID={existing_doc.id})")
                    continue

                # 1. 创建 Document 记录
                subjects = db.query(Subject).all()
                subject_id = None
                subject_name = None
                stem = filepath.stem
                candidate = stem.split("_", 1)[-1] if "_" in stem else stem
                for subject in subjects:
                    if subject.name and subject.name in stem:
                        subject_id = subject.id
                        subject_name = subject.name
                        break
                    if subject.name and subject.name == candidate:
                        subject_id = subject.id
                        subject_name = subject.name
                        break

                doc = Document(
                    filename=filepath.name,
                    parsing_status=ParsingStatus.INDEXING,
                    source="system",
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    size_bytes=filepath.stat().st_size,
                    metadata_json={
                        "subject_id": subject_id,
                        "subject_name": subject_name,
                    },
                )
                db.add(doc)
                db.commit()
                db.refresh(doc)
                
                # 2. 复制文件到 documents/{id}/
                doc_dir = STORAGE_DIR / "documents" / str(doc.id)
                doc_dir.mkdir(parents=True, exist_ok=True)
                dest_path = doc_dir / f"orig{filepath.suffix}"
                dest_path.write_bytes(filepath.read_bytes())
                doc.file_path = str(dest_path)
                
                # 3. 解析文档
                raw_content = filepath.read_bytes()
                pages = parse_document(raw_content, filepath.name)
                chunks = chunk_pages(doc.id, pages, chunk_size=800, overlap=200)
                
                # 4. 向量化
                texts = [str(c.get("text", "")) for c in chunks]
                embeddings = embedding_provider.embed_texts(texts)
                
                # 5. 存入 ChromaDB
                if chunks:
                    upsert_ids = cast(Any, [c["id"] for c in chunks])
                    upsert_embeddings = cast(Any, embeddings)
                    upsert_metadatas = cast(
                        Any,
                        [
                            {
                                "document_id": doc.id,
                                "page": c["page"],
                                "chunk_id": c["id"],
                                "order": c["order"],
                                **({"subject_id": subject_id} if subject_id is not None else {}),
                                **({"subject_name": subject_name} if subject_name else {}),
                            }
                            for c in chunks
                        ],
                    )
                    upsert_documents = cast(Any, [str(c.get("text", "")) for c in chunks])

                    collection.upsert(
                        ids=upsert_ids,
                        embeddings=upsert_embeddings,
                        metadatas=upsert_metadatas,
                        documents=upsert_documents,
                    )
                
                # 6. 更新状态
                doc.metadata_json = {
                    "page_count": len(pages),
                    "chunk_count": len(chunks),
                    "subject_id": subject_id,
                    "subject_name": subject_name,
                }
                doc.parsing_status = ParsingStatus.READY
                db.commit()
                
                print(f"[OK] ID={doc.id}, {len(chunks)} chunks")
                success += 1
                    
        except Exception as e:
            print(f"[FAIL] {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"导入完成！成功: {success}, 失败: {failed}")
    print("=" * 50)
    
    # 统计
    with SessionLocal() as db:
        total_docs = db.query(Document).count()
    print(f"\n数据库文档数: {total_docs}")
    print(f"ChromaDB 向量数: {collection.count()}")


if __name__ == "__main__":
    seed()
