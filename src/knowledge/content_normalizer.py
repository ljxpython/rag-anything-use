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
        current["metadata"].update(
            document_id=document_id,
            filename=filename,
            chunk_id=f"{document_id}:chunk:{index}",
        )
        current["metadata"].pop("page_index", None)
        current["metadata"].pop("page_index_end", None)
        page = current.get("page_idx")
        page_end = current.get("page_idx_end", page)
        if type(page) is int and page >= 0:
            current["metadata"]["page_index"] = page
            if type(page_end) is int and page <= page_end:
                current["metadata"]["page_index_end"] = page_end
            else:
                current.pop("page_idx_end", None)
        else:
            current.pop("page_idx", None)
            current.pop("page_idx_end", None)
        normalized.append(current)
    return normalized
