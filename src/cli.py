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
from src.knowledge.document_registry import KnowledgeDocumentRegistry
from src.knowledge.publication import (
    model_signature,
    namespace_lock,
    validate_publication,
)
from src.knowledge.schemas import ProjectKnowledgeQueryRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAGAnything knowledge devtools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="导入知识文档")
    ingest_parser.add_argument("--project-id", required=True)
    ingest_parser.add_argument("--file", required=True)

    publish_parser = subparsers.add_parser(
        "publish", help="发布离线索引；之后仅可查询，新资料必须建新 namespace"
    )
    publish_parser.add_argument("--project-id", required=True)

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

    init_parser = subparsers.add_parser(
        "init-project-knowledge", help="注册逻辑项目库（管理员）"
    )
    init_parser.add_argument("--tenant-id", required=True)
    init_parser.add_argument("--project-id", required=True)
    migrate_parser = subparsers.add_parser(
        "migrate-project-knowledge", help="保留旧文档ID迁移完整索引（管理员）"
    )
    migrate_parser.add_argument("--knowledge-base-id", required=True)
    migrate_parser.add_argument("--namespace", required=True)
    migrate_parser.add_argument(
        "--processing-signature", required=True, help="核对历史全部处理配置后确认的签名"
    )
    activate_parser = subparsers.add_parser(
        "activate-knowledge-generation", help="关闭/开启上传或显式回退（管理员）"
    )
    activate_parser.add_argument("--knowledge-base-id", required=True)
    activate_parser.add_argument("--namespace")
    activate_parser.add_argument("--uploads", choices=["on", "off"])

    return parser


async def _main_async(args: argparse.Namespace) -> int:
    config = build_knowledge_service_config()
    rag_engine = ProjectRAGEngine(config)
    try:
        return await _execute(args, rag_engine)
    finally:
        await rag_engine.close()


async def _execute(args: argparse.Namespace, rag_engine: ProjectRAGEngine) -> int:
    if args.command in {
        "init-project-knowledge",
        "migrate-project-knowledge",
        "activate-knowledge-generation",
    }:
        from src.knowledge.jobs import KnowledgeJobStore
        from src.knowledge.generations import KnowledgeGenerationService
        from src.knowledge.project_admin import KnowledgeProjectAdmin

        store = KnowledgeJobStore(rag_engine.config)
        generations = KnowledgeGenerationService(store, rag_engine)
        admin = KnowledgeProjectAdmin(store, generations)
        try:
            if args.command == "init-project-knowledge":
                result = admin.register(args.tenant_id, args.project_id)
            elif args.command == "migrate-project-knowledge":
                result = await admin.migrate(
                    args.knowledge_base_id, args.namespace, args.processing_signature
                )
            else:
                if args.uploads == "off":
                    store.enable(args.knowledge_base_id, False)
                if args.namespace:
                    await generations.rollback(args.knowledge_base_id, args.namespace)
                if args.uploads == "on":
                    store.enable(args.knowledge_base_id, True)
                if not args.namespace and not args.uploads:
                    raise ValueError("knowledge_activation_action_required")
                project = store.project(args.knowledge_base_id)
                result = {
                    "knowledge_base_id": project["id"],
                    "namespace": project["active_namespace"],
                    "revision": project["revision"],
                    "upload_enabled": bool(project["enabled"]),
                }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        finally:
            await generations.close()
    ingest_service = KnowledgeIngestService(rag_engine=rag_engine)
    query_service = KnowledgeQueryService(rag_engine=rag_engine)
    admin_service = KnowledgeAdminService(rag_engine=rag_engine)

    if args.command == "ingest":
        result = await ingest_service.ingest_document(
            project_id=args.project_id,
            file_path=args.file,
        )
    elif args.command == "publish":
        paths = rag_engine.get_project_paths(args.project_id)
        with namespace_lock(paths, write=True):
            records = KnowledgeDocumentRegistry(paths).list_documents(limit=10000)
            if (
                not paths.rag_workdir.is_dir()
                or not records
                or any(
                    r.overall_status != "ready" or r.index_status != "ready"
                    for r in records
                )
            ):
                raise ValueError("knowledge_index_not_ready")
            marker = paths.manifest_dir / "publication.json"
            if marker.exists():
                validate_publication(paths)
            else:
                with marker.open("x", encoding="utf-8") as handle:
                    json.dump(model_signature(), handle)
            result = {"status": "published", "document_count": len(records)}
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
    return 1 if getattr(result, "accepted", True) is False else 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
