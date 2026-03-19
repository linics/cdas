from app.api.v2.evaluations import _compute_average_score, _normalize_dimension_scores


def test_normalize_dimension_scores_clamps() -> None:
    dims = [{"name": "维度A"}, {"name": "维度B"}]
    raw = {"维度A": 5, "维度B": 0}
    normalized = _normalize_dimension_scores(dims, raw, fallback=2)
    assert normalized["维度A"] == 4
    assert normalized["维度B"] == 1


def test_compute_average_score_rounds() -> None:
    assert _compute_average_score({"维度A": 4, "维度B": 3}) == 4
    assert _compute_average_score({"维度A": 2, "维度B": 3}) == 3
