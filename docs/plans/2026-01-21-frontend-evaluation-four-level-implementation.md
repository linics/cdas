# Frontend Evaluation Four-Level Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace 0–100 scoring with 1–4 four-level sliders for dimension scores and total evaluation, using Chinese labels, and make backend accept only `score_numeric`.

**Architecture:** Add Vitest + React Testing Library for UI checks, update GradingPage to use 1–4 sliders, remove level dropdown, and update backend evaluation model to derive `score_level` from `score_numeric`.

**Tech Stack:** React + React Query + Vite (frontend), FastAPI + Pydantic (backend), Vitest + RTL (tests)

---

### Task 1: Add frontend test tooling and a failing UI test

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/pages/__tests__/GradingPage.test.tsx`
- Create: `frontend/src/setupTests.ts`
- Create: `frontend/vitest.config.ts`

**Step 1: Add Vitest/RTL deps and test scripts**

```json
"devDependencies": {
  "vitest": "^1.6.0",
  "@testing-library/react": "^14.2.0",
  "@testing-library/jest-dom": "^6.4.2",
  "@testing-library/user-event": "^14.5.2",
  "jsdom": "^24.0.0"
},
"scripts": {
  "test": "vitest",
  "test:run": "vitest run"
}
```

**Step 2: Add test setup**

```ts
import '@testing-library/jest-dom';
```

**Step 3: Add vitest config**

```ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.ts'],
  },
});
```

**Step 4: Write failing test**

```tsx
import { render, screen } from '@testing-library/react';
import GradingPage from '../GradingPage';

vi.mock('react-router-dom', () => ({
  useParams: () => ({ submissionId: '1' }),
  useNavigate: () => vi.fn(),
}));

vi.mock('@tanstack/react-query', () => ({
  useQuery: () => ({
    data: {
      data: {
        id: 1,
        assignment_id: 1,
        phase_index: 0,
        content_json: {},
        attachments_json: [],
        checkpoints_json: {},
      },
    },
  }),
  useMutation: () => ({ mutate: vi.fn(), isPending: false }),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

vi.mock('../lib/api', () => ({
  submissionsApi: { getById: vi.fn() },
  assignmentsApi: {
    getById: vi.fn(),
  },
  evaluationsApi: {
    aiAssist: vi.fn(),
    createTeacher: vi.fn(),
  },
}));

test('renders four-level sliders with Chinese labels', () => {
  render(<GradingPage />);
  const sliders = screen.getAllByRole('slider');
  for (const slider of sliders) {
    expect(slider).toHaveAttribute('min', '1');
    expect(slider).toHaveAttribute('max', '4');
    expect(slider).toHaveAttribute('step', '1');
  }
  expect(screen.getByText('优秀')).toBeInTheDocument();
  expect(screen.getByText('良好')).toBeInTheDocument();
  expect(screen.getByText('合格')).toBeInTheDocument();
  expect(screen.getByText('需改进')).toBeInTheDocument();
});
```

**Step 5: Run test to verify it fails**

Run: `npm run test:run` (in `frontend/`)  
Expected: FAIL due to current sliders using 0–100 and missing labels.

**Step 6: Commit**

```bash
git add frontend/package.json frontend/vitest.config.ts frontend/src/setupTests.ts frontend/src/pages/__tests__/GradingPage.test.tsx
git commit -m "test: add vitest and failing rubric slider check"
```

---

### Task 2: Update frontend grading UI to four-level sliders

**Files:**
- Modify: `frontend/src/pages/GradingPage.tsx`

**Step 1: Add score label helper**

```tsx
const scoreLabels: Record<number, string> = {
  1: '需改进',
  2: '合格',
  3: '良好',
  4: '优秀',
};
```

**Step 2: Change dimension slider**

```tsx
<input
  type="range"
  min="1"
  max="4"
  step="1"
  value={evaluation.dimension_scores_json?.[dim.name] || 1}
  onChange={(e) => handleDimensionScoreChange(dim.name, Number(e.target.value))}
/>
<span>{scoreLabels[evaluation.dimension_scores_json?.[dim.name] || 1]}</span>
```

**Step 3: Replace total score with slider**

```tsx
<input
  type="range"
  min="1"
  max="4"
  step="1"
  value={evaluation.score_numeric ?? 3}
  onChange={(e) => setEvaluation(prev => ({ ...prev, score_numeric: Number(e.target.value) }))}
/>
<div>{scoreLabels[evaluation.score_numeric ?? 3]}</div>
```

**Step 4: Remove level dropdown and update submit payload**

```tsx
submitEvalMutation.mutate({
  submission_id: Number(submissionId),
  score_numeric: evaluation.score_numeric,
  feedback: evaluation.feedback || '',
  dimension_scores_json: evaluation.dimension_scores_json,
});
```

**Step 5: Run tests**

Run: `npm run test:run` (in `frontend/`)  
Expected: PASS.

**Step 6: Commit**

```bash
git add frontend/src/pages/GradingPage.tsx
git commit -m "feat: use four-level sliders for evaluation"
```

---

### Task 3: Update backend to accept only numeric score

**Files:**
- Modify: `app/api/v2/evaluations.py`
- Modify: `frontend/src/lib/api.ts`
- Create: `tests/test_evaluation_score_numeric.py`

**Step 1: Make score_level optional in API model**

```python
class TeacherEvaluationCreate(BaseModel):
    submission_id: int
    score_numeric: int
    score_level: Optional[EvaluationLevel] = None
    ...
```

**Step 2: Derive score_level from score_numeric**

```python
level_map = {4: EvaluationLevel.EXCELLENT, 3: EvaluationLevel.GOOD, 2: EvaluationLevel.PASS, 1: EvaluationLevel.IMPROVE}
if data.score_numeric not in level_map:
    raise HTTPException(status_code=400, detail="score_numeric must be 1-4")
score_level = data.score_level or level_map[data.score_numeric]
```

**Step 3: Update frontend API type**

```ts
export interface TeacherEvaluationCreate {
  submission_id: number;
  score_numeric: number;
  score_level?: "A" | "B" | "C" | "D";
  ...
}
```

**Step 4: Add failing backend test**

```python
def test_teacher_evaluation_uses_numeric_only(client, session):
    # create teacher + submission
    # send payload with only score_numeric=4
    # assert response score_level derived as "A"
```

**Step 5: Run test**

Run: `pytest tests/test_evaluation_score_numeric.py::test_teacher_evaluation_uses_numeric_only -v`  
Expected: FAIL before implementation, PASS after.

**Step 6: Commit**

```bash
git add app/api/v2/evaluations.py frontend/src/lib/api.ts tests/test_evaluation_score_numeric.py
git commit -m "feat: derive evaluation level from numeric score"
```

---

### Task 4: Verification

**Step 1: Run backend tests**

Run: `pytest -q`  
Expected: PASS.

**Step 2: Run frontend tests**

Run: `npm run test:run` (in `frontend/`)  
Expected: PASS.

**Step 3: Manual sanity check**
- Open grading page and confirm sliders show 1–4 and Chinese labels
- Total evaluation uses single slider only
