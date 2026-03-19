from __future__ import annotations

from enum import Enum
from typing import Iterable, Optional


class EvidenceType(str, Enum):
    TEXT = "text"
    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    CONFIRM = "confirm"
    LINK = "link"


EVIDENCE_TYPE_VALUES = {item.value for item in EvidenceType}


def normalize_trimmed(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()



def normalize_optional_text(value: object) -> Optional[str]:
    text = normalize_trimmed(value)
    return text or None



def normalize_int_list(values: Iterable[object] | None) -> list[int]:
    if values is None:
        return []
    normalized: list[int] = []
    seen: set[int] = set()
    for raw in values:
        try:
            value = int(str(raw))
        except Exception:
            continue
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized
