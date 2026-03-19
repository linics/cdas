from app.api.v2.assignments import RubricDimensionSchema


def test_rubric_dimension_accepts_levels() -> None:
    dim = RubricDimensionSchema(
        name="维度A",
        levels={
            "excellent": "优秀",
            "good": "良好",
            "pass": "合格",
            "improve": "需改进",
        },
    )
    assert dim.name == "维度A"
    assert "excellent" in dim.levels
