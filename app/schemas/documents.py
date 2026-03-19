"""Inventory 相关的 API 响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.models import ParsingStatus


class DocumentUploadResponse(BaseModel):
    document_id: int = Field(validation_alias="id")
    filename: str
    parsing_status: ParsingStatus = Field(serialization_alias="status")

    model_config = {"from_attributes": True}


class DocumentListItem(BaseModel):
    id: int
    filename: str
    parsing_status: ParsingStatus = Field(serialization_alias="status")
    upload_date: datetime
    metadata_json: Optional[Dict[str, Any]] = None
    source: str = "user"

    model_config = {"from_attributes": True}


class DocumentDetail(BaseModel):
    id: int
    filename: str
    parsing_status: ParsingStatus = Field(serialization_alias="status")
    upload_date: datetime
    metadata_json: Optional[Dict[str, Any]] = None
    error_msg: Optional[str] = None
    file_path: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    source: str = "user"

    model_config = {"from_attributes": True}
