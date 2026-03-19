# Frontend Archive UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Apply the “academic archive” visual system across all frontend pages while keeping page-level differentiation.

**Architecture:** Centralize theme tokens and base layout in global styles, then layer page-specific styles per route. Reuse card/section classes for consistent paper-like surfaces.

**Tech Stack:** React, Vite, CSS

---

### Task 1: Add global theme tokens and base styles

**Files:**
- Modify: `frontend/src/index.css`
- Modify: `frontend/src/App.css`

**Step 1: Write the failing test**

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import App from "../App";

test("app root renders with archive ui class", () => {
  render(
    <MemoryRouter>
      <App />
    </MemoryRouter>
  );
  expect(document.body.classList.contains("archive-ui")).toBe(true);
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test:run -- frontend/src/pages/__tests__/GradingPage.test.tsx`  
Expected: FAIL because the class is not set.

**Step 3: Write minimal implementation**

```tsx
// frontend/src/App.tsx
import { useEffect } from "react";

export default function App() {
  useEffect(() => {
    document.body.classList.add("archive-ui");
    return () => document.body.classList.remove("archive-ui");
  }, []);
  ...
}
```

```css
/* frontend/src/index.css */
:root {
  --paper: #f7f3ea;
  --ink: #1f2b2a;
  --deep: #1f3b4d;
  --accent: #b88a3b;
  --muted: #7c7a73;
  --edge: rgba(31, 43, 42, 0.12);
  --shadow: 0 10px 30px rgba(28, 30, 26, 0.12);
  --radius: 14px;
}

body.archive-ui {
  background: radial-gradient(circle at 20% 0%, #fff7e6, #f5f1e6 45%, #efe9dc 100%);
  color: var(--ink);
  font-family: "IBM Plex Sans", system-ui, sans-serif;
}
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test:run -- frontend/src/pages/__tests__/GradingPage.test.tsx`  
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/index.css frontend/src/App.css
git commit -m "Add archive UI base theme tokens"
```

---

### Task 2: Style shared cards, headers, and controls

**Files:**
- Modify: `frontend/src/App.css`
- Modify: `frontend/src/components/ui/button.tsx`
- Modify: `frontend/src/components/ui/card.tsx`
- Modify: `frontend/src/pages/LoginPage.css`

**Step 1: Write the failing test**

```tsx
import { render } from "@testing-library/react";
import { Button } from "../../components/ui/button";

test("button uses archive class", () => {
  const { container } = render(<Button>Action</Button>);
  const button = container.querySelector("button");
  expect(button?.className).toContain("archive-button");
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test:run -- frontend/src/pages/__tests__/GradingPage.test.tsx`  
Expected: FAIL because class is not present.

**Step 3: Write minimal implementation**

```tsx
// frontend/src/components/ui/button.tsx
const classes = cn(
  "archive-button",
  "inline-flex items-center justify-center ...",
  className
);
```

```tsx
// frontend/src/components/ui/card.tsx
return (
  <div className={cn("archive-card", className)} {...props} />
);
```

```css
/* frontend/src/App.css */
.archive-card {
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid var(--edge);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  backdrop-filter: blur(6px);
}

.archive-button {
  background: var(--deep);
  color: #fff;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.2);
}
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test:run -- frontend/src/pages/__tests__/GradingPage.test.tsx`  
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/App.css frontend/src/components/ui/button.tsx frontend/src/components/ui/card.tsx frontend/src/pages/LoginPage.css
git commit -m "Style archive UI cards and buttons"
```

---

### Task 3: Apply page-specific layouts (login/register, lists, grading)

**Files:**
- Modify: `frontend/src/pages/LoginPage.tsx`
- Modify: `frontend/src/pages/RegisterPage.tsx`
- Modify: `frontend/src/pages/AssignmentsPage.tsx`
- Modify: `frontend/src/pages/GradingPage.tsx`
- Modify: `frontend/src/pages/EvaluationsPage.tsx`

**Step 1: Write the failing test**

```tsx
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import LoginPage from "../LoginPage";

test("login page uses archive cover class", () => {
  const { container } = render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>
  );
  expect(container.querySelector(".archive-cover")).toBeTruthy();
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test:run -- frontend/src/pages/__tests__/GradingPage.test.tsx`  
Expected: FAIL because the class is missing.

**Step 3: Write minimal implementation**

Add wrapper classes like `archive-cover`, `archive-list`, `archive-review` and wire page-specific layouts with small layout changes (section headers, badge labels, table-like spacing).

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test:run -- frontend/src/pages/__tests__/GradingPage.test.tsx`  
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/pages/LoginPage.tsx frontend/src/pages/RegisterPage.tsx frontend/src/pages/AssignmentsPage.tsx frontend/src/pages/GradingPage.tsx frontend/src/pages/EvaluationsPage.tsx
git commit -m "Apply archive UI layouts to key pages"
```

---

### Task 4: Validate remaining pages with shared classes

**Files:**
- Modify: `frontend/src/pages/AssignmentPage.tsx`
- Modify: `frontend/src/pages/AssignmentDesignPage.tsx`
- Modify: `frontend/src/pages/AssignmentSubmissionsPage.tsx`
- Modify: `frontend/src/pages/StudentSubmissionPage.tsx`
- Modify: `frontend/src/pages/StudentEvaluationPage.tsx`
- Modify: `frontend/src/pages/InventoryPage.tsx`
- Modify: `frontend/src/pages/KnowledgeBasePage.tsx`
- Modify: `frontend/src/pages/GroupsPage.tsx`
- Modify: `frontend/src/pages/SubmissionPage.tsx`
- Modify: `frontend/src/pages/MyAssignmentsPage.tsx`

**Step 1: Write the failing test**

```tsx
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AssignmentPage from "../AssignmentPage";

test("assignment page uses archive section class", () => {
  const { container } = render(
    <MemoryRouter>
      <AssignmentPage />
    </MemoryRouter>
  );
  expect(container.querySelector(".archive-section")).toBeTruthy();
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test:run -- frontend/src/pages/__tests__/GradingPage.test.tsx`  
Expected: FAIL.

**Step 3: Write minimal implementation**

Add shared wrappers (`archive-section`, `archive-panel`, `archive-meta`) to the remaining pages and wire class usage to existing containers.

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test:run -- frontend/src/pages/__tests__/GradingPage.test.tsx`  
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/pages/*.tsx
git commit -m "Apply archive UI wrappers to remaining pages"
```

---

### Task 5: Full frontend verification

**Step 1: Run frontend tests**

Run: `npm --prefix frontend run test:run`  
Expected: PASS.

**Step 2: Run backend tests (optional sanity)**

Run: `pytest -q`  
Expected: PASS (warnings ok).

**Step 3: Commit (if needed)**

```bash
git add frontend/src
git commit -m "Finalize archive UI styling"
```

---

Plan complete and saved to `docs/plans/2026-01-21-frontend-archive-ui-implementation.md`. Two execution options:

1. Subagent-Driven (this session) - I dispatch fresh subagent per task, review between tasks, fast iteration
2. Parallel Session (separate) - Open new session with executing-plans, batch execution with checkpoints

Which approach?
