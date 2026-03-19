"""文档解析与文本切片工具。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Dict, List, Sequence

from docx import Document as DocxDocument
from pypdf import PdfReader


class UnsupportedDocumentError(ValueError):
    """不支持的文件类型。"""


def parse_document(content: bytes, filename: str) -> List[Dict[str, str]]:
    """根据文件后缀解析为按页的文本列表。

    返回 ``[{\"page\": int, \"text\": str}, ...]``。页码采用 1-based。
    """

    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(content)
    if suffix in {".docx", ".doc"}:
        return _parse_docx(content)
    if suffix in {".txt", ""}:
        return _parse_plain(content)
    raise UnsupportedDocumentError(f"Unsupported file extension: {suffix}")


def _parse_pdf(content: bytes) -> List[Dict[str, str]]:
    reader = PdfReader(BytesIO(content))
    pages: List[Dict[str, str]] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append({"page": idx, "text": text})
    return pages


def _parse_docx(content: bytes) -> List[Dict[str, str]]:
    doc = DocxDocument(BytesIO(content))
    text = "\n".join(p.text for p in doc.paragraphs)
    return [{"page": 1, "text": text}]


def _parse_plain(content: bytes) -> List[Dict[str, str]]:
    return [{"page": 1, "text": content.decode("utf-8", errors="ignore")}]


def chunk_pages(
    document_id: int,
    pages: Sequence[Dict[str, str]],
    chunk_size: int = 800,
    overlap: int = 200,
) -> List[Dict[str, object]]:
    """将按页文本切片为带重叠的 chunk 列表。

    chunk_id 采用 ``{document_id}-{page}-{order}``。
    """

    chunks: List[Dict[str, object]] = []
    for page in pages:
        tokens = page["text"].split()
        if not tokens:
            continue
        start = 0
        order = 0
        while start < len(tokens):
            end = min(len(tokens), start + chunk_size)
            chunk_tokens = tokens[start:end]
            chunk_text = " ".join(chunk_tokens)
            chunk_id = f"{document_id}-{page['page']}-{order}"
            chunks.append(
                {
                    "id": chunk_id,
                    "page": page["page"],
                    "order": order,
                    "text": chunk_text,
                    "token_count": len(chunk_tokens),
                }
            )
            if end == len(tokens):
                break
            start = max(0, end - overlap)
            order += 1
    return chunks
