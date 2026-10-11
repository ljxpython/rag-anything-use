from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.knowledge.config import KnowledgeServiceConfig


@dataclass(frozen=True)
class KnowledgeProjectPaths:
    root_dir: Path
    project_dir: Path
    manifest_dir: Path
    parser_dir: Path
    rag_workdir: Path
    debug_dir: Path

    def as_path_list(self) -> list[Path]:
        return [
            self.root_dir,
            self.project_dir,
            self.manifest_dir,
            self.parser_dir,
            self.rag_workdir,
            self.debug_dir,
        ]


def build_knowledge_project_paths(
    project_id: str, config: KnowledgeServiceConfig
) -> KnowledgeProjectPaths:
    if not isinstance(project_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", project_id
    ):
        raise ValueError("invalid_knowledge_namespace")
    root_dir = config.root_dir.expanduser().resolve()
    project_dir = (root_dir / project_id).resolve()
    if not project_dir.is_relative_to(root_dir):
        raise ValueError("knowledge_path_escape")
    for name in ("manifest", "parser", "rag_workdir", "debug"):
        if not (project_dir / name).resolve().is_relative_to(project_dir):
            raise ValueError("knowledge_path_escape")
    return KnowledgeProjectPaths(
        root_dir=root_dir,
        project_dir=project_dir,
        manifest_dir=project_dir / "manifest",
        parser_dir=project_dir / "parser",
        rag_workdir=project_dir / "rag_workdir",
        debug_dir=project_dir / "debug",
    )
