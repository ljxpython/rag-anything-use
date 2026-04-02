from __future__ import annotations

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
    normalized_project_id = str(project_id).strip()
    if not normalized_project_id:
        raise ValueError("project_id_required")
    root_dir = config.root_dir.expanduser()
    project_dir = root_dir / normalized_project_id
    return KnowledgeProjectPaths(
        root_dir=root_dir,
        project_dir=project_dir,
        manifest_dir=project_dir / "manifest",
        parser_dir=project_dir / "parser",
        rag_workdir=project_dir / "rag_workdir",
        debug_dir=project_dir / "debug",
    )
