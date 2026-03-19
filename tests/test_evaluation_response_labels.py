from app.api.v2.evaluations import _build_dimension_labels


def test_build_dimension_labels() -> None:
    scores = {"维度A": 4, "维度B": 2}
    labels = _build_dimension_labels(scores)
    assert labels["维度A"] == "优秀"
    assert labels["维度B"] == "合格"
