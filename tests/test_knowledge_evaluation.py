import pytest

from scripts.evaluate_knowledge import score_sources
from scripts.verify_document_formats import evidence_found


def test_format_table_evidence_does_not_pass_from_body_text():
    question = "What is the P1 response time in the severity table?"
    assert not evidence_found(
        question, "7 minutes", [{"preview": "Incident response: 7 minutes."}]
    )
    assert evidence_found(
        question, "7 minutes", [{"preview": "Table Analysis:\n| P1 | 7 minutes |"}]
    )


def test_evaluation_uses_document_specific_truncated_evidence():
    expected = {"a.md": ["fact A"], "b.md": ["fact B"]}
    ids = {"a.md": "a", "b.md": "b"}
    one = [{"document_id": "a", "preview": "fact A and fact B"}]
    result = score_sources(expected, one, ids)
    assert result["document_recall"] == 0.5
    assert result["evidence_complete"] is False
    assert result["cross_project_sources"] == 0
    assert result["first_relevant_rank"] == 1
    both = one + [{"document_id": "b", "preview": "fact B"}]
    assert score_sources(expected, both, ids)["evidence_complete"] is True
    assert score_sources({}, both, ids)["evidence_complete"] is None
    assert (
        score_sources({}, [{"document_id": "other", "preview": "x"}], ids)[
            "cross_project_sources"
        ]
        == 1
    )
    with pytest.raises(ValueError, match="expected_document_missing"):
        score_sources({"missing.md": ["x"]}, both, ids)
