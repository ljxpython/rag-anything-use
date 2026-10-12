from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from raganything import RAGAnything


@dataclass(frozen=True)
class ParsedKnowledgeDocument:
    parser_name: str
    source_path: Path
    content_list: list[dict[str, Any]] = field(default_factory=list)
    source_document_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class DoclingParserAdapter:
    def __init__(self, *, rag: RAGAnything, parser_name: str = "docling") -> None:
        self.rag = rag
        self.parser_name = parser_name

    async def parse_file(self, file_path: str | Path) -> ParsedKnowledgeDocument:
        path = Path(file_path).expanduser().resolve()
        parse_result = await self.rag.parse_document(str(path))
        content_list: list[dict[str, Any]] = []
        source_document_id: str | None = None
        metadata: dict[str, Any] = {}
        if isinstance(parse_result, tuple):
            if len(parse_result) != 2 or not isinstance(parse_result[0], list):
                raise TypeError("invalid_knowledge_parse_result")
            content_list = list(parse_result[0])
            if isinstance(parse_result[1], str):
                source_document_id = parse_result[1]
            elif isinstance(parse_result[1], dict):
                metadata = dict(parse_result[1])
            else:
                raise TypeError("invalid_knowledge_parse_result")
        elif isinstance(parse_result, list):
            content_list = list(parse_result)
        else:
            raise TypeError(
                f"unexpected_parse_result_type:{type(parse_result).__name__}"
            )
        if any(not isinstance(item, dict) for item in content_list):
            raise TypeError("invalid_knowledge_content_block")
        return ParsedKnowledgeDocument(
            parser_name=self.parser_name,
            source_path=path,
            content_list=content_list,
            source_document_id=source_document_id,
            metadata=metadata,
        )


def build_docling_parser():
    from raganything.parser import DoclingParser

    class ProvenanceParser(DoclingParser):
        def read_from_block(self, block, type, output_dir, cnt, num):
            result = super().read_from_block(block, type, output_dir, cnt, num)
            if result.get("type") == "table" and isinstance(result["table_body"], dict):
                from docling_core.types.doc.document import TableData
                from raganything.utils import format_table_body

                # Feed cell text to prompts/previews, not geometry and serializer fields.
                table = TableData.model_validate(result["table_body"])
                result["table_body"] = format_table_body(
                    [
                        [
                            cell.text.replace("\n", " ").replace("|", "\\|")
                            for cell in row
                        ]
                        for row in table.grid
                    ]
                )
            pages = [
                p["page_no"] - 1
                for p in block.get("prov") or []
                if isinstance(p, dict)
                and isinstance(p.get("page_no"), int)
                and not isinstance(p["page_no"], bool)
                and p["page_no"] > 0
            ]
            result.pop("page_idx", None)
            if pages:
                result.update(page_idx=min(pages), page_idx_end=max(pages))
            return result

    return ProvenanceParser()
