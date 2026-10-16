import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class LocatorResolver:
    """Enterprise multi-format locator resolver for precision document provenance.

    Extracts verified 1-based page numbers, slide indices, and block types from
    Docling raw output and .blocks.jsonl sidecars.
    """

    def __init__(self, data_root: Optional[Path] = None):
        self.data_root = Path(data_root) if data_root else None
        # doc_id -> parsed metadata dict
        self._doc_cache: Dict[str, Dict[str, Any]] = {}

    def register_sidecar_data(self, doc_id: str, data: Dict[str, Any]) -> None:
        """Explicitly registers parsed sidecar data into the resolver cache."""
        self._doc_cache[doc_id] = data

    def _load_doc_data(self, doc_id: str) -> Dict[str, Any]:
        """Loads sidecar metadata from cache or scans the filesystem data_root."""
        if doc_id in self._doc_cache:
            return self._doc_cache[doc_id]

        if not self.data_root or not self.data_root.exists():
            return {}

        # 1. Search for raw docling JSON first (highest precision)
        raw_candidates = list(self.data_root.glob(f"**/*{doc_id}*/*.json"))
        if not raw_candidates:
            raw_candidates = list(self.data_root.glob(f"**/{doc_id}.json"))

        for cand in raw_candidates:
            try:
                data = json.loads(cand.read_text(encoding="utf-8"))
                if "texts" in data or "tables" in data or "body" in data:
                    res = {"type": "docling_raw", "data": data}
                    self._doc_cache[doc_id] = res
                    return res
            except Exception:
                pass

        # 2. Search for .blocks.jsonl sidecar
        sidecar_candidates = list(
            self.data_root.glob(f"**/*{doc_id}*.blocks.jsonl")
        )
        if not sidecar_candidates:
            sidecar_candidates = list(self.data_root.glob("**/*.blocks.jsonl"))

        blocks = []
        if sidecar_candidates:
            target_file = sidecar_candidates[0]
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                blocks.append(json.loads(line))
                            except Exception:
                                pass
                if blocks:
                    res = {"type": "sidecar", "blocks": blocks}
                    self._doc_cache[doc_id] = res
                    return res
            except Exception:
                pass

        return {}

    def resolve_locator(
        self, doc_id: str, file_path: str, chunk_content: str
    ) -> Dict[str, Any]:
        """Resolves precision locator conforming strictly to platform _Locator schema."""
        ext = Path(file_path).suffix.lower()

        # Format dispatching
        if ext in (".pptx", ".ppt"):
            unit = "slide"
        elif ext in (".pdf", ".docx"):
            unit = "page"
        else:
            # Markdown, plain text or unsupported types do not guess page/slide
            return {
                "unit": "unknown",
                "start": None,
                "end": None,
                "block_type": None,
            }

        doc_meta = self._load_doc_data(doc_id)
        if not doc_meta:
            # Fallback to page/slide 1 if document is of pagination type but sidecar absent
            return {
                "unit": unit,
                "start": 1,
                "end": 1,
                "block_type": "text",
            }

        matched_pages: Set[int] = set()
        matched_types: List[str] = []
        chunk_clean = self._clean_text(chunk_content)

        if doc_meta.get("type") == "docling_raw":
            raw_doc = doc_meta["data"]

            # 1. Match against text blocks
            for item in raw_doc.get("texts", []):
                t_text = self._clean_text(item.get("text", ""))
                if not t_text:
                    continue
                if self._matches(t_text, chunk_clean):
                    for prov in item.get("prov", []):
                        p_no = prov.get("page_no")
                        if p_no is not None:
                            try:
                                matched_pages.add(int(p_no))
                            except (ValueError, TypeError):
                                pass
                    matched_types.append("text")

            # 2. Match against tables
            for tbl in raw_doc.get("tables", []):
                # Search table text representation or cells
                tbl_text = self._clean_text(str(tbl))
                if self._matches(tbl_text, chunk_clean):
                    for prov in tbl.get("prov", []):
                        p_no = prov.get("page_no")
                        if p_no is not None:
                            try:
                                matched_pages.add(int(p_no))
                            except (ValueError, TypeError):
                                pass
                    matched_types.append("table")

            # 3. Match against pictures / diagrams
            for pic in raw_doc.get("pictures", []):
                pic_caption = self._clean_text(str(pic.get("caption", "")))
                if pic_caption and self._matches(pic_caption, chunk_clean):
                    for prov in pic.get("prov", []):
                        p_no = prov.get("page_no")
                        if p_no is not None:
                            try:
                                matched_pages.add(int(p_no))
                            except (ValueError, TypeError):
                                pass
                    matched_types.append("image")

        elif doc_meta.get("type") == "sidecar":
            for b in doc_meta.get("blocks", []):
                if b.get("type") != "content":
                    continue
                b_content = self._clean_text(b.get("content", ""))
                if not b_content:
                    continue
                if self._matches(b_content, chunk_clean):
                    for pos in b.get("positions", []):
                        anchor = pos.get("anchor")
                        if anchor:
                            # Anchor may be a list of strings like ["1"] or a single string "1"
                            anchors = (
                                anchor if isinstance(anchor, list) else [anchor]
                            )
                            for page_str in anchors:
                                try:
                                    matched_pages.add(int(page_str))
                                except (ValueError, TypeError):
                                    pass
                    matched_types.append(b.get("block_type") or "text")

        if not matched_pages:
            # Fallback to page 1 if from pagination document
            return {
                "unit": unit,
                "start": 1,
                "end": 1,
                "block_type": "text",
            }

        start_page = min(matched_pages)
        end_page = max(matched_pages)
        # Ensure valid range constraint: start <= end and start >= 1
        start_page = max(1, start_page)
        end_page = max(start_page, end_page)

        block_type = (
            matched_types[0]
            if matched_types and matched_types[0] in ("text", "table", "image", "equation")
            else "text"
        )

        return {
            "unit": unit,
            "start": start_page,
            "end": end_page,
            "block_type": block_type,
        }

    @staticmethod
    def _clean_text(text: str) -> str:
        """Removes newlines and redundant spaces, converting to lowercase."""
        if not text:
            return ""
        return " ".join(text.replace("\r", " ").replace("\n", " ").split()).lower()

    @staticmethod
    def _matches(a: str, b: str) -> bool:
        """Robust multi-tier matching (exact, substring, or significant phrase)."""
        if not a or not b:
            return False
        if a in b or b in a:
            return True
        # Split into substantial phrases (>= 15 chars)
        phrases = [p.strip() for p in a.split(". ") if len(p.strip()) >= 15]
        return any(p in b for p in phrases)
