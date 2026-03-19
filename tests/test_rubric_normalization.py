from app.api.v2.assignments import _default_rubric, _normalize_ai_assignment_output
from app.models.enums import AssignmentType


def test_normalize_rubric_adds_levels_when_missing() -> None:
    payload = {
        "rubric": {"dimensions": [{"name": "维度A", "description": "旧描述"}]}
    }
    normalized = _normalize_ai_assignment_output(payload)
    dims = normalized["rubric"]["dimensions"]
    assert dims[0]["name"] == "维度A"
    assert "levels" in dims[0]


def test_default_rubric_uses_levels_only() -> None:
    rubric = _default_rubric(AssignmentType.PRACTICAL)
    assert "dimensions" in rubric
    assert "levels" in rubric["dimensions"][0]
    assert "weight" not in rubric["dimensions"][0]
