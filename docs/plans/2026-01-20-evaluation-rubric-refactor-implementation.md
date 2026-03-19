# Evaluation Rubric Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace v2 rubric/evaluation logic with 4-level scoring and labels aligned to the product design, removing weight-based and 0–100 scoring.

**Architecture:** Update rubric generation/normalization to use `levels` per dimension, adjust evaluation enums and scoring to 1–4 with label mapping, and update AI prompts plus normalization to support legacy inputs safely.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy, pytest

---

### Task 1: Add rubric-level defaults and normalization helpers

**Files:**
- Modify: `app/api/v2/assignments.py`
- Test: `tests/test_rubric_normalization.py`

**Step 1: Write the failing test**

```python
from app.api.v2.assignments import _normalize_ai_assignment_output, _default_rubric
from app.models.enums import AssignmentType

def test_normalize_rubric_adds_levels_when_missing():
    payload = {
        "rubric": {"dimensions": [{"name": "维度A", "description": "旧描述"}]}
    }
    normalized = _normalize_ai_assignment_output(payload)
    dims = normalized["rubric"]["dimensions"]
    assert dims[0]["name"] == "维度A"
    assert "levels" in dims[0]

def test_default_rubric_uses_levels_only():
    rubric = _default_rubric(AssignmentType.PRACTICAL)
    assert "dimensions" in rubric
    assert "levels" in rubric["dimensions"][0]
    assert "weight" not in rubric["dimensions"][0]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_rubric_normalization.py -v`  
Expected: FAIL (missing `levels` / weight still present)

**Step 3: Write minimal implementation**

- Update `_default_rubric` to return `dimensions: [{name, levels}]` with four Chinese labels.
- Update `_generate_ai_content` prompt to request 4-level rubric (remove weight mention).
- Update `_normalize_ai_assignment_output` to:
  - Accept list/criteria formats and normalize to `dimensions`.
  - Ensure each dimension has `levels`; if missing, add default labels.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_rubric_normalization.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_rubric_normalization.py app/api/v2/assignments.py
git commit -m "refactor: update rubric defaults and normalization to 4-level"
```

---

### Task 2: Update evaluation enums and scoring utilities

**Files:**
- Modify: `app/models/enums.py`
- Modify: `app/models/submission.py`
- Modify: `app/db.py`
- Test: `tests/test_evaluation_scoring.py`

**Step 1: Write the failing test**

```python
from app.api.v2.evaluations import _score_to_level, _level_label, _normalize_level_input

def test_level_label_mapping():
    assert _level_label("excellent") == "优秀"
    assert _level_label("good") == "良好"
    assert _level_label("pass") == "合格"
    assert _level_label("improve") == "需改进"

def test_normalize_level_input():
    assert _normalize_level_input("A") == "excellent"
    assert _normalize_level_input(4) == "excellent"
    assert _normalize_level_input(2) == "pass"

def test_score_to_level_numeric():
    assert _score_to_level(4) == "excellent"
    assert _score_to_level(1) == "improve"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_evaluation_scoring.py -v`  
Expected: FAIL (helpers not implemented / old enum)

**Step 3: Write minimal implementation**

- Update `EvaluationLevel` in `app/models/enums.py` to `EXCELLENT/GOOD/PASS/IMPROVE`.
- Update comments in `app/models/submission.py` to describe 1–4 scoring.
- Update `app/db.py` to remove or adjust `score_level` uppercasing to avoid mismatched values.
- Add helper functions in `app/api/v2/evaluations.py`:
  - `_level_label`
  - `_normalize_level_input`
  - `_score_to_level` using 1–4

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_evaluation_scoring.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add app/models/enums.py app/models/submission.py app/db.py app/api/v2/evaluations.py tests/test_evaluation_scoring.py
git commit -m "refactor: update evaluation levels to 4-tier scheme"
```

---

### Task 3: Update AI evaluation prompt and normalization

**Files:**
- Modify: `app/api/v2/evaluations.py`
- Test: `tests/test_ai_evaluation_normalization.py`

**Step 1: Write the failing test**

```python
from app.api.v2.evaluations import _normalize_dimension_scores, _compute_average_score

def test_normalize_dimension_scores_clamps():
    dims = [{"name": "维度A"}, {"name": "维度B"}]
    raw = {"维度A": 5, "维度B": 0}
    normalized = _normalize_dimension_scores(dims, raw, fallback=2)
    assert normalized["维度A"] == 4
    assert normalized["维度B"] == 1

def test_compute_average_score_rounds():
    assert _compute_average_score({"维度A": 4, "维度B": 3}) == 4
    assert _compute_average_score({"维度A": 2, "维度B": 3}) == 3
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_ai_evaluation_normalization.py -v`  
Expected: FAIL (helpers not implemented)

**Step 3: Write minimal implementation**

- Update AI prompt to request 1–4 scoring and Chinese label.
- Replace `_compute_weighted_score` with simple average helper.
- Add `_normalize_dimension_scores` and `_compute_average_score`.
- Ensure fallback uses default score 2 (合格).
- Ensure AI output is normalized to 1–4 and mapped to enum/labels.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_ai_evaluation_normalization.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add app/api/v2/evaluations.py tests/test_ai_evaluation_normalization.py
git commit -m "refactor: update AI evaluation normalization to 4-level scoring"
```

---

### Task 4: Update API schemas and response labels

**Files:**
- Modify: `app/api/v2/evaluations.py`
- Test: `tests/test_evaluation_response_labels.py`

**Step 1: Write the failing test**

```python
from app.api.v2.evaluations import _level_label, _build_dimension_labels

def test_build_dimension_labels():
    scores = {"维度A": 4, "维度B": 2}
    labels = _build_dimension_labels(scores)
    assert labels["维度A"] == "优秀"
    assert labels["维度B"] == "合格"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_evaluation_response_labels.py -v`  
Expected: FAIL (helpers not implemented)

**Step 3: Write minimal implementation**

- Update `EvaluationResponse` to include:
  - `score_level_label`
  - `dimension_level_labels`
- Add helper `_build_dimension_labels` based on 1–4 → label mapping.
- Ensure responses populate these fields for teacher/self/peer as applicable.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_evaluation_response_labels.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add app/api/v2/evaluations.py tests/test_evaluation_response_labels.py
git commit -m "feat: add evaluation label fields to responses"
```

---

### Task 5: Documentation alignment (optional, if needed)

**Files:**
- Modify: `docs/PRODUCT_DESIGN.md`
- Modify: `docs/PRODUCT_DESIGN_SUPPLEMENT.md` (if required)

**Step 1: Verify docs match API structure**

Run: `rg -n "rubric|评价|四档" docs/PRODUCT_DESIGN.md docs/PRODUCT_DESIGN_SUPPLEMENT.md`

**Step 2: Update wording if needed**

Only adjust if the implementation meaning diverges from the doc text.

**Step 3: Commit**

```bash
git add docs/PRODUCT_DESIGN.md docs/PRODUCT_DESIGN_SUPPLEMENT.md
git commit -m "docs: align rubric and evaluation descriptions"
```

---

### Task 6: Final verification

**Step 1: Run targeted tests**

Run:  
`pytest tests/test_rubric_normalization.py tests/test_evaluation_scoring.py tests/test_ai_evaluation_normalization.py tests/test_evaluation_response_labels.py -v`

Expected: PASS  

**Step 2: (Optional) Full test suite**

Run: `pytest`  
Expected: may still fail due to integration tests requiring a running server; report status.

**Step 3: Commit remaining changes**

```bash
git status -sb
```

