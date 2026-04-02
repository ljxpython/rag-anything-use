from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def normalize_content_list(
    content_list: Iterable[dict[str, Any]],
    *,
    document_id: str,
    filename: str,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(content_list, start=1):
        current = dict(item)
        metadata = current.get("metadata")
        current["metadata"] = dict(metadata) if isinstance(metadata, dict) else {}
        current["metadata"].setdefault("document_id", document_id)
        current["metadata"].setdefault("filename", filename)
        current["metadata"].setdefault("chunk_id", f"{document_id}:chunk:{index}")
        if "page_idx" in current and "page_index" not in current["metadata"]:
            current["metadata"]["page_index"] = current["page_idx"]
        normalized.append(current)
    return normalized
