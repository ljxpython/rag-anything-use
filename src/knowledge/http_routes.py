"""Custom HTTP routes explicitly authenticate; FastMCP auth does not cover them."""

from __future__ import annotations

import asyncio
import json

from starlette.responses import JSONResponse

from src.knowledge.upload_service import safe_error


def register_knowledge_routes(server, verifier, uploads):
    async def scope_for(request):
        bearer = request.headers.get("authorization", "")
        token = bearer[7:] if bearer.startswith("Bearer ") else ""
        access = await verifier.verify_token(token)
        if access is None:
            raise ValueError("knowledge_authorization_denied")
        scope = verifier.token_scopes[token]
        uploads.scope_project(scope)
        return scope

    def failure(exc):
        code = safe_error(exc)
        status = (
            401
            if code == "knowledge_authorization_denied"
            else 404
            if code == "knowledge_not_found"
            else 413
            if code == "knowledge_file_too_large"
            else 415
            if code == "knowledge_unsupported_format"
            else 409
            if code
            in {"knowledge_content_conflict", "knowledge_processing_config_changed"}
            else 400
        )
        return JSONResponse(
            {
                "error": {"code": code, "message": code, "details": [], "extra": None},
                "request_id": None,
            },
            status_code=status,
        )

    @server.custom_route("/internal/knowledge/uploads/{request_id}", methods=["PUT"])
    async def upload(request):
        try:
            scope = await scope_for(request)
            metadata = request.headers.get("x-knowledge-file-ref", "")
            if len(metadata.encode()) > 4096:
                raise ValueError("invalid_file_ref")
            ref = json.loads(metadata)
            if request.headers.get("content-type", "").split(";")[0] != ref.get(
                "mime_type"
            ):
                raise ValueError("knowledge_unsupported_format")
            length = request.headers.get("content-length")
            if length and int(length) > uploads.config.max_file_bytes:
                raise ValueError("knowledge_file_too_large")
            result = await uploads.stage_upload(
                scope,
                request.path_params["request_id"],
                ref,
                request.headers.get("x-knowledge-operation-grant", ""),
                request.stream(),
            )
            return JSONResponse(result)
        except Exception as exc:
            return failure(exc)

    @server.custom_route("/internal/knowledge/uploads/{request_id}", methods=["GET"])
    async def lookup_upload(request):
        try:
            scope = await scope_for(request)
            if request.query_params:
                raise ValueError("invalid_file_ref")
            return JSONResponse(
                await asyncio.to_thread(
                    uploads.lookup_request,
                    scope,
                    request.path_params["request_id"],
                    request.headers.get("x-knowledge-operation-grant", ""),
                )
            )
        except Exception as exc:
            return failure(exc)

    @server.custom_route("/internal/knowledge/capabilities", methods=["GET"])
    async def capabilities(request):
        try:
            scope = await scope_for(request)
            return JSONResponse(await asyncio.to_thread(uploads.capabilities, scope))
        except Exception as exc:
            return failure(exc)

    async def listing(request, jobs):
        try:
            scope = await scope_for(request)
            if set(request.query_params) - {"limit", "offset"}:
                raise ValueError("invalid_file_ref")
            limit = int(request.query_params.get("limit", "20"))
            offset = int(request.query_params.get("offset", "0"))
            if not 1 <= limit <= 100 or offset < 0:
                raise ValueError("invalid_file_ref")
            method = uploads.store.list_jobs if jobs else uploads.store.list_documents
            return JSONResponse(
                await asyncio.to_thread(method, scope.knowledge_base_id, limit, offset)
            )
        except Exception as exc:
            return failure(exc)

    @server.custom_route("/internal/knowledge/documents", methods=["GET"])
    async def documents(request):
        return await listing(request, False)

    @server.custom_route("/internal/knowledge/jobs", methods=["GET"])
    async def jobs(request):
        return await listing(request, True)

    @server.custom_route("/internal/knowledge/jobs/{job_id}", methods=["GET"])
    async def job(request):
        try:
            scope = await scope_for(request)
            return JSONResponse(
                await asyncio.to_thread(
                    uploads.store.receipt,
                    scope.knowledge_base_id,
                    request.path_params["job_id"],
                )
            )
        except Exception as exc:
            return failure(exc)
