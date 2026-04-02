from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_KNOWLEDGE_ROOT_DIRNAME = "knowledge_data"
DEFAULT_KNOWLEDGE_PARSER = "docling"
DEFAULT_KNOWLEDGE_QUERY_MODE = "hybrid"
DEFAULT_KNOWLEDGE_TOP_K = 8
DEFAULT_KNOWLEDGE_INCLUDE_CITATIONS = True
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class KnowledgeServiceConfig:
    root_dir: Path
    parser_name: str = DEFAULT_KNOWLEDGE_PARSER
    parse_method: str = "auto"
    query_default_mode: str = DEFAULT_KNOWLEDGE_QUERY_MODE
    query_default_top_k: int = DEFAULT_KNOWLEDGE_TOP_K
    include_citations_by_default: bool = DEFAULT_KNOWLEDGE_INCLUDE_CITATIONS
    enable_image_processing: bool = False
    enable_table_processing: bool = False
    enable_equation_processing: bool = False


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def build_knowledge_service_config() -> KnowledgeServiceConfig:
    root_override = os.getenv("KNOWLEDGE_ROOT_DIR", "").strip()
    root_dir = (
        Path(root_override).expanduser()
        if root_override
        else PROJECT_ROOT / DEFAULT_KNOWLEDGE_ROOT_DIRNAME
    )
    return KnowledgeServiceConfig(
        root_dir=root_dir,
        parser_name=os.getenv("PARSER", DEFAULT_KNOWLEDGE_PARSER),
        parse_method=os.getenv("PARSE_METHOD", "auto"),
        query_default_mode=os.getenv("KNOWLEDGE_QUERY_MODE", DEFAULT_KNOWLEDGE_QUERY_MODE),
        query_default_top_k=_parse_int(
            os.getenv("KNOWLEDGE_TOP_K"), DEFAULT_KNOWLEDGE_TOP_K
        ),
        include_citations_by_default=_parse_bool(
            os.getenv("KNOWLEDGE_INCLUDE_CITATIONS"),
            DEFAULT_KNOWLEDGE_INCLUDE_CITATIONS,
        ),
        enable_image_processing=_parse_bool(
            os.getenv("KNOWLEDGE_ENABLE_IMAGE_PROCESSING"),
            False,
        ),
        enable_table_processing=_parse_bool(
            os.getenv("KNOWLEDGE_ENABLE_TABLE_PROCESSING"),
            False,
        ),
        enable_equation_processing=_parse_bool(
            os.getenv("KNOWLEDGE_ENABLE_EQUATION_PROCESSING"),
            False,
        ),
    )
