import json
import tempfile
from pathlib import Path
from typing import Literal
import pytest
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.knowledge.locator_resolver import LocatorResolver


# Platform contract models (extracted verbatim from runtime_service/tools/knowledge.py)
class _Locator(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit: Literal["page", "slide", "unknown"]
    start: int | None = Field(strict=True, ge=1)
    end: int | None = Field(strict=True, ge=1)
    block_type: Literal["text", "image", "table", "equation"] | None

    @model_validator(mode="after")
    def valid_range(self):
        if self.unit == "unknown":
            if self.start is not None or self.end is not None:
                raise ValueError("unknown_locator_range")
        elif self.start is None or self.end is None or self.start > self.end:
            raise ValueError("invalid_locator_range")
        return self


def test_locator_pdf_single_and_multi_page():
    resolver = LocatorResolver()
    doc_id = "kd_pdf_sample_001"

    # Mock Docling Raw JSON
    sidecar_data = {
        "type": "docling_raw",
        "data": {
            "texts": [
                {
                    "text": "Executive Summary: Q3 Financial Performance and Metrics.",
                    "prov": [{"page_no": 1}],
                },
                {
                    "text": "Detailed Breakdown: Infrastructure Costs and Capital Expenditure.",
                    "prov": [{"page_no": 2}],
                },
                {
                    "text": "Conclusion and Next Steps for Engineering.",
                    "prov": [{"page_no": 3}],
                },
            ],
            "tables": [
                {
                    "text": "Revenue breakdown table: APAC 40%, EMEA 35%, NA 25%.",
                    "prov": [{"page_no": 2}],
                }
            ],
            "pictures": [],
        },
    }
    resolver.register_sidecar_data(doc_id, sidecar_data)

    # 1. Query matching single page (Page 1)
    loc1 = resolver.resolve_locator(
        doc_id, "finance_report.pdf", "Executive Summary: Q3 Financial Performance"
    )
    validated1 = _Locator.model_validate(loc1)
    assert validated1.unit == "page"
    assert validated1.start == 1
    assert validated1.end == 1
    assert validated1.block_type == "text"

    # 2. Query spanning across multiple pages (Page 1 and Page 2)
    spanning_text = (
        "Executive Summary: Q3 Financial Performance and Metrics. "
        "Detailed Breakdown: Infrastructure Costs and Capital Expenditure."
    )
    loc_multi = resolver.resolve_locator(
        doc_id, "finance_report.pdf", spanning_text
    )
    validated_multi = _Locator.model_validate(loc_multi)
    assert validated_multi.unit == "page"
    assert validated_multi.start == 1
    assert validated_multi.end == 2
    assert validated_multi.block_type == "text"

    # 3. Query matching table (Page 2)
    loc_table = resolver.resolve_locator(
        doc_id, "finance_report.pdf", "Revenue breakdown table: APAC 40%"
    )
    validated_table = _Locator.model_validate(loc_table)
    assert validated_table.unit == "page"
    assert validated_table.start == 2
    assert validated_table.end == 2
    assert validated_table.block_type == "table"


def test_locator_pptx_slide():
    resolver = LocatorResolver()
    doc_id = "kd_pptx_sample_002"

    # Mock Sidecar blocks.jsonl
    sidecar_data = {
        "type": "sidecar",
        "blocks": [
            {
                "type": "content",
                "content": "Slide 5: Architecture Blueprint of Orion Gateway.",
                "positions": [{"anchor": ["5"]}],
                "block_type": "text",
            },
            {
                "type": "content",
                "content": "Slide 12: Deployment Topology and VPC peering.",
                "positions": [{"anchor": ["12"]}],
                "block_type": "text",
            },
        ],
    }
    resolver.register_sidecar_data(doc_id, sidecar_data)

    loc_pptx = resolver.resolve_locator(
        doc_id, "architecture_deck.pptx", "Architecture Blueprint of Orion Gateway"
    )
    validated_pptx = _Locator.model_validate(loc_pptx)
    assert validated_pptx.unit == "slide"
    assert validated_pptx.start == 5
    assert validated_pptx.end == 5
    assert validated_pptx.block_type == "text"


def test_locator_markdown_and_plain_text():
    resolver = LocatorResolver()
    doc_id = "kd_md_sample_003"

    # Markdown / TXT documents must return unit="unknown" with null ranges
    loc_md = resolver.resolve_locator(
        doc_id, "operations.md", "Production environment backup policy"
    )
    validated_md = _Locator.model_validate(loc_md)
    assert validated_md.unit == "unknown"
    assert validated_md.start is None
    assert validated_md.end is None
    assert validated_md.block_type is None


def test_locator_filesystem_autoloading():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        doc_id = "kd_auto_004"
        doc_dir = root / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)

        # Write docling JSON to disk
        json_file = doc_dir / "sample.json"
        json_file.write_text(
            json.dumps(
                {
                    "texts": [
                        {
                            "text": "Disk autoloader test page 7 content.",
                            "prov": [{"page_no": 7}],
                        }
                    ]
                }
            )
        )

        resolver = LocatorResolver(data_root=root)
        loc = resolver.resolve_locator(
            doc_id, "sample.pdf", "Disk autoloader test page 7 content"
        )
        validated = _Locator.model_validate(loc)
        assert validated.unit == "page"
        assert validated.start == 7
        assert validated.end == 7
        assert validated.block_type == "text"
