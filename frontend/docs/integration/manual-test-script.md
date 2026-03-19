# Manual Test Script (QA Handoff)

Release-gate command matrix reference:

- `docs/integration/release-gate-checklist.md`

## 1) Environment Prep

- Backend: `http://127.0.0.1:8000` is running
- Frontend: run from `frontend`
  - `npm install`
  - `npm run dev`
- Browser opens `http://127.0.0.1:5173`

Recommended test accounts per run:

- Teacher username: `teacher_<timestamp>`
- Student username: `student_<timestamp>`
- Password: at least 8 chars (example `Passw0rd!`)

## 2) Auth Flow

### A. Teacher Register + Login

1. Open `/auth`
2. Select `我是教师`
3. Switch to register mode
4. Fill name + teacher id + password, submit
5. Expect redirect to teacher dashboard `/`
6. Logout, then login using same teacher id/password
7. Expect login success and dashboard visible

### B. Student Register + Login

1. Open `/auth`
2. Select `我是学生`
3. Switch to register mode
4. Fill name + student id + grade + class + password, submit
5. Expect redirect to student dashboard `/student`
6. Logout, then login using same student id/password
7. Expect login success and student dashboard visible

## 3) Teacher Assignment Flow

1. Login as teacher
2. Open `设计作业` (`/create`)
3. Fill required fields (title/topic/main subject/steps)
4. Click `保存草稿`
5. Expect success notice and history list contains this assignment as `草稿`
6. Click `发布作业`
7. Expect assignment status changes to `已发布`

Expected result:

- Dashboard stats update (draft/published)
- Assignment visible in recent list with `查看提交` and `编辑` actions

## 4) Student Submission Flow

1. Login as student
2. In `/student`, locate published assignment and click `进入任务`
3. If no submission exists, click `开始作业`
4. Input content, add at least one attachment link
5. Click `保存草稿`
6. Click `提交本阶段`

Expected result:

- Current phase becomes submitted
- If phased mode, next phase draft auto-created and opened
- Submission chips show phase progression and statuses

## 5) Teacher Grading Flow

1. Login as teacher
2. Open dashboard recent assignment -> `查看提交`
3. Select a submitted phase, click `进入评分`
4. Optionally click `AI 辅助`
5. Adjust dimension sliders and final score
6. Fill feedback and click `提交评分`

Expected result:

- Success notice shown
- Submission status and teacher evaluation available in assignment detail

## 6) Student Feedback Flow

1. Login as student
2. Open the same assignment and phase
3. Check right-side `教师反馈`

Expected result:

- Score level + numeric score + feedback text are visible

## 7) Knowledge Base Flow

1. Login as teacher
2. Open `知识库` (`/knowledge`)
3. Upload a small `.txt/.doc/.docx/.pdf` file
4. Wait for status transition to `已入库`
5. Delete the uploaded file

Expected result:

- Upload succeeds, status updates to ready state
- File is removable and list refreshes correctly

## 8) Route Boundary Checks

### Student account

- Visit `/create`, `/classes`, `/grading/<id>`, `/knowledge`
- Expect redirect to `/student`

### Teacher account

- Visit `/student`
- Expect redirect to `/`

### Unknown route

- Visit `/xxx-not-found`
- Expect 404 page with return action

## 9) Pass Criteria

- No blocking page errors in console for core flows
- All core workflows succeed without manual DB edits
- Knowledge base upload reaches ready state in current backend setup
- Remaining deferred features remain explicitly marked (profile/settings persistence, advanced collaboration deep parity, notification/search integration)
