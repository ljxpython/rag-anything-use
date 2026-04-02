from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from raganything import RAGAnything


@dataclass(frozen=True)
class ParsedKnowledgeDocument:
    parser_name: str
    source_path: Path
    content_list: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class DoclingParserAdapter:
    def __init__(self, *, rag: RAGAnything, parser_name: str = "docling") -> None:
        self.rag = rag
        self.parser_name = parser_name

    async def parse_file(self, file_path: str | Path) -> ParsedKnowledgeDocument:
        path = Path(file_path).expanduser().resolve()
        parse_result = await self.rag.parse_document(str(path))
        content_list: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {}
        if isinstance(parse_result, tuple):
            if len(parse_result) >= 1 and isinstance(parse_result[0], list):
                content_list = list(parse_result[0])
            if len(parse_result) >= 2 and isinstance(parse_result[1], dict):
                metadata = dict(parse_result[1])
        elif isinstance(parse_result, list):
            content_list = list(parse_result)
        else:
            raise RuntimeError(f"unexpected_parse_result_type:{type(parse_result).__name__}")
        return ParsedKnowledgeDocument(
            parser_name=self.parser_name,
            source_path=path,
            content_list=content_list,
            metadata=metadata,
        )
