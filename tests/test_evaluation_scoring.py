from app.api.v2.evaluations import _level_label, _normalize_level_input, _score_to_level


def test_level_label_mapping() -> None:
    assert _level_label("excellent") == "优秀"
    assert _level_label("good") == "良好"
    assert _level_label("pass") == "合格"
    assert _level_label("improve") == "需改进"


def test_normalize_level_input() -> None:
    assert _normalize_level_input("A") == "excellent"
    assert _normalize_level_input(4) == "excellent"
    assert _normalize_level_input(2) == "pass"


def test_score_to_level_numeric() -> None:
    assert _score_to_level(4) == "excellent"
    assert _score_to_level(1) == "improve"
