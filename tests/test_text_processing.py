from __future__ import annotations

import app.utils.text_processing as text_processing


def test_parse_document_routes_legacy_doc_files_through_docx_reader(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_parse_docx(content: bytes):
        captured["content"] = content
        return [{"page": 1, "text": "legacy"}]

    monkeypatch.setattr(text_processing, "_parse_docx", fake_parse_docx)

    result = text_processing.parse_document(b"legacy-doc", "legacy.doc")

    assert result == [{"page": 1, "text": "legacy"}]
    assert captured["content"] == b"legacy-doc"
