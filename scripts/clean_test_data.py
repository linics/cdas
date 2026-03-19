"""清理测试数据，重置 RAG 知识库。"""
import argparse
import shutil
import sys
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import SessionLocal, engine
from app.models import Document, Assignment, ProjectGroup, Submission
from chromadb import PersistentClient

STORAGE_DIR = Path(__file__).parent.parent / "storage"


def clean():
    print("=" * 50)
    print("清理 RAG 知识库测试数据")
    print("=" * 50)
    
    # 1. 清空数据库
    print("\n[1/3] 清空数据库...")
    with SessionLocal() as db:
        sub_count = db.query(Submission).delete()
        group_count = db.query(ProjectGroup).delete()
        assign_count = db.query(Assignment).delete()
        doc_count = db.query(Document).delete()
        db.commit()
        print(f"  删除 Submission: {sub_count} 条")
        print(f"  删除 ProjectGroup: {group_count} 条")
        print(f"  删除 Assignment: {assign_count} 条")
        print(f"  删除 Document: {doc_count} 条")
    print("  ✓ 数据库已清空")
    
    # 2. 清空 ChromaDB
    print("\n[2/3] 清空 ChromaDB...")
    chroma_path = STORAGE_DIR / "chroma"
    if chroma_path.exists():
        chroma = PersistentClient(path=str(chroma_path))
        try:
            coll = chroma.get_collection("cdas-documents")
            count = coll.count()
            chroma.delete_collection("cdas-documents")
            print(f"  删除 cdas-documents 集合: {count} 个向量")
        except ValueError:
            print("  集合不存在，跳过")
    print("  ✓ ChromaDB 已清空")
    
    # 3. 删除 documents/1-7
    print("\n[3/3] 删除测试文件夹 (1-7)...")
    docs_dir = STORAGE_DIR / "documents"
    deleted = 0
    for i in range(1, 8):
        folder = docs_dir / str(i)
        if folder.exists():
            shutil.rmtree(folder)
            print(f"  删除 {folder.name}/")
            deleted += 1
    print(f"  ✓ 已删除 {deleted} 个测试文件夹")
    
    print("\n" + "=" * 50)
    print("清理完成！")
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dangerous full cleanup for local disposable environments only")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Acknowledge destructive cleanup of assignment/document data",
    )
    args = parser.parse_args()

    if not args.force:
        print("Refusing to run destructive cleanup without --force")
        print("Use selective cleanup instead: python scripts/clean_integration_artifacts.py")
        raise SystemExit(2)

    clean()
