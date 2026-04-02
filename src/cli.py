from __future__ import annotations

import argparse
import asyncio
import json

from src.knowledge import (
    KnowledgeAdminService,
    KnowledgeIngestService,
    KnowledgeQueryService,
    ProjectRAGEngine,
    build_knowledge_service_config,
)
from src.knowledge.schemas import ProjectKnowledgeQueryRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAGAnything knowledge devtools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="导入知识文档")
    ingest_parser.add_argument("--project-id", required=True)
    ingest_parser.add_argument("--file", required=True)

    query_parser = subparsers.add_parser("query", help="查询项目知识库")
    query_parser.add_argument("--project-id", required=True)
    query_parser.add_argument("--query", required=True)
    query_parser.add_argument("--top-k", type=int, default=8)
    query_parser.add_argument("--mode", default="hybrid")

    debug_query_parser = subparsers.add_parser(
        "debug-retrieve",
        help="查看项目知识库检索上下文",
    )
    debug_query_parser.add_argument("--project-id", required=True)
    debug_query_parser.add_argument("--query", required=True)
    debug_query_parser.add_argument("--top-k", type=int, default=8)
    debug_query_parser.add_argument("--mode", default="hybrid")

    list_parser = subparsers.add_parser("list-docs", help="列出知识文档")
    list_parser.add_argument("--project-id", required=True)
    list_parser.add_argument("--status", default=None)
    list_parser.add_argument("--limit", type=int, default=20)

    doc_status_parser = subparsers.add_parser("doc-status", help="查看文档状态")
    doc_status_parser.add_argument("--project-id", required=True)
    doc_status_parser.add_argument("--document-id", required=True)

    return parser


async def _main_async(args: argparse.Namespace) -> int:
    config = build_knowledge_service_config()
    rag_engine = ProjectRAGEngine(config)
    ingest_service = KnowledgeIngestService(rag_engine=rag_engine)
    query_service = KnowledgeQueryService(rag_engine=rag_engine)
    admin_service = KnowledgeAdminService(rag_engine=rag_engine)

    if args.command == "ingest":
        result = await ingest_service.ingest_document(
            project_id=args.project_id,
            file_path=args.file,
        )
    elif args.command == "query":
        result = await query_service.query_project_knowledge(
            ProjectKnowledgeQueryRequest(
                project_id=args.project_id,
                query=args.query,
                top_k=args.top_k,
                mode=args.mode,
                include_citations=True,
            )
        )
    elif args.command == "debug-retrieve":
        result = await rag_engine.debug_retrieve(
            ProjectKnowledgeQueryRequest(
                project_id=args.project_id,
                query=args.query,
                top_k=args.top_k,
                mode=args.mode,
                include_citations=True,
                include_debug_chunks=True,
            )
        )
    elif args.command == "list-docs":
        result = admin_service.list_project_documents(
            project_id=args.project_id,
            status=args.status,
            limit=args.limit,
        )
    elif args.command == "doc-status":
        result = admin_service.get_document_status(
            project_id=args.project_id,
            document_id=args.document_id,
        )
    else:
        raise ValueError(f"unsupported_command:{args.command}")

    if hasattr(result, "model_dump_json"):
        print(result.model_dump_json(indent=2, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
