# CDAS 前端重设计接口说明

最后更新：2026-03-24

## 1. 文档定位

本文档面向前端重设计后的实现与联调，整理当前前端真实依赖的后端接口、请求约束、响应结构和页面使用关系。

它回答的是“新前端页面落地时，需要如何与后端对接”，不回答页面应该长什么样。页面结构与交互目标请配合以下文档一起使用：

- [FRONTEND_REDESIGN_REQUIREMENTS.md](/Users/linics/Documents/githubfiles/cdas/docs/FRONTEND_REDESIGN_REQUIREMENTS.md)
- [FRONTEND_REDESIGN_SPEC.md](/Users/linics/Documents/githubfiles/cdas/docs/FRONTEND_REDESIGN_SPEC.md)

## 2. 来源与可信度说明

本文档基于以下材料整理：

- `frontend/src/app/lib/api.ts`
- `frontend/src/app/context/AuthContext.tsx`
- `frontend/src/app/pages/*.tsx`
- `frontend/src/app/validation/*.ts`
- `frontend/docs/integration/api-contract-governance.md`
- `docs/PRODUCT_DESIGN.md`

说明：

- 这是“当前前端消费视角”的接口文档。
- 它足够支持重设计后的前端实现和 UI 联调。
- 若后端已经新增但前端尚未消费的接口，本文档不会主动覆盖。

## 3. 全局对接约束

## 3.1 基础 URL

| 项 | 规则 |
| --- | --- |
| API 基础地址 | 来自 `VITE_API_BASE_URL` |
| 未配置基础地址时 | 使用相对路径 |
| 主要业务接口前缀 | `/api/v2` |
| 文档接口前缀 | `/api/documents` |

## 3.2 认证规则

| 项 | 规则 |
| --- | --- |
| token 存储键 | `cdas_token` |
| 默认是否带鉴权 | 是 |
| 未登录接口 | `register`、`login` |
| 鉴权头 | `Authorization: Bearer {token}` |
| `401` 行为 | 清除 token，并派发 `cdas-auth-invalid` 事件 |

前端设计与实现必须考虑以下体验：

- token 过期后，页面可能在下一次请求失败时自动回到未登录态
- 所有需要登录的页面都必须支持“会话失效后跳回登录页”

## 3.3 通用错误处理

| 项 | 规则 |
| --- | --- |
| 成功响应 | 优先按 `application/json` 解析 |
| 失败响应消息 | 优先读取 `detail` |
| 默认超时 | `30000ms` |
| 教案生成接口超时 | `90000ms` |
| 网络异常文案 | `网络异常，请检查后端服务是否启动` |
| 超时文案 | `请求超时，请稍后重试` |

前端重设计时应确保：

- 每个关键页面都有加载态、失败态、重试能力
- 错误消息尽量展示后端 `detail`
- 不要把所有失败都压缩成“操作失败”

## 3.4 合同治理要求

来自 `frontend/docs/integration/api-contract-governance.md` 的关键约束：

- `snake_case` 命名保持稳定
- 日期时间统一 ISO 8601 字符串
- `/api/v2` 视为稳定合同
- 默认策略是“读兼容、写收紧”
- 前端应容忍新增可选字段
- 对旧数据要提供 defensive defaults

## 4. 核心数据模型

## 4.1 用户 `ApiUser`

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `id` | number | 用户主键 |
| `username` | string | 登录名，教师为工号、学生为学号 |
| `role` | `teacher \| student` | 路由分流、权限判断 |
| `name` | string | 页面展示名 |
| `grade` | number/null | 学生作业筛选 |
| `class_name` | string/null | 学生注册信息展示 |

## 4.2 学科 `Subject`

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `id` | number | 主学科/融合学科选择 |
| `code` | string | 学科编码 |
| `name` | string | UI 展示 |
| `category` | string | 学科分类 |
| `primary_available` | boolean | 小学可用 |
| `middle_available` | boolean | 初中可用 |
| `core_competencies` | array | 现有 UI 未直接使用，但后续可扩展 |

## 4.3 班级 `Classroom`

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `id` | number | 班级标识 |
| `name` | string | 班级名称 |
| `grade` | number | 班级年级 |
| `invite_code` | string | 学生入班 |
| `teacher_id` | number | 归属教师 |
| `teacher_name` | string/null | 学生端展示教师 |
| `member_count` | number | 成员数展示 |
| `joined_group_id` | number/null | 学生当前班级小组 |
| `joined_group_name` | string/null | 学生当前班级小组名 |
| `created_at` | string | 时间展示 |
| `updated_at` | string | 时间展示 |

## 4.4 作业 `Assignment`

重设计后所有作业相关页面都依赖该结构。

必需重点保留的字段：

- `id`
- `title`
- `topic`
- `description`
- `school_stage`
- `grade`
- `main_subject_id`
- `related_subject_ids`
- `assignment_type`
- `practical_subtype`
- `inquiry_subtype`
- `inquiry_depth`
- `submission_mode`
- `duration_weeks`
- `deadline`
- `objectives_json`
- `phases_json`
- `rubric_json`
- `is_published`
- `is_archived`
- `document_id`
- `created_at`

对 UI 影响最大的三个嵌套字段：

### `objectives_json`

当前前端使用：

- `knowledge`
- `process`
- `emotion`

注意：

- 设计器会把 `process` 中的“背景设定”拆出来单独编辑，再合并回去

### `phases_json`

结构上至少包含：

- `name`
- `order`
- `title`
- `steps`

而每个 `step` 至少包含：

- `name`
- `description`
- `checkpoints`
- `content`

当前学生提交页、教师详情页、批改页都依赖它来渲染阶段任务。

### `rubric_json`

当前前端重点消费：

- `dimensions[].name`

虽然结构支持 `levels/description/weight`，但现有 UI 主要使用维度名称与维度数。

## 4.5 作业小组 `AssignmentGroup`

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `id` | number | 作业小组 ID |
| `assignment_id` | number | 所属作业 |
| `name` | string | 小组名 |
| `members_json` | array | 组员列表 |

`members_json` 内当前重点使用：

- `user_id`
- `name`
- `username`

## 4.6 提交 `Submission`

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `id` | number | submission ID |
| `assignment_id` | number | 所属作业 |
| `student_id` | number | 提交人 |
| `group_id` | number/null | 小组提交标识 |
| `group_name` | string/null | 小组名 |
| `group_members` | array | 小组成员展示 |
| `phase_index` | number | 阶段定位 |
| `step_index` | number/null | 现 UI 未重点使用 |
| `status` | `draft/submitted/graded` | 编辑性与展示状态 |
| `content_json` | object | 文本主体 |
| `attachments_json` | array | 附件列表 |
| `checkpoints_json` | object | 检查点完成情况 |
| `created_at` | string | 时间展示 |
| `submitted_at` | string/null | 最近提交时间 |
| `teacher_evaluated_at` | string/null | 最近评分时间 |
| `next_submission_id` | number/null | 下一阶段跳转 |

## 4.7 评价 `Evaluation`

当前前端界面主要消费教师评价。

重点字段：

- `submission_id`
- `evaluation_type`
- `score_level`
- `score_numeric`
- `dimension_scores_json`
- `score_level_label`
- `dimension_level_labels`
- `feedback`
- `created_at`

## 4.8 文档 `DocumentItem`

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `id` | number | 文档 ID |
| `filename` | string | 文件名 |
| `status` | enum | 文档状态 |
| `parsing_status` | enum | 兼容状态字段 |
| `upload_date` | string | 上传时间 |
| `metadata_json` | object | chunk 数等扩展元信息 |
| `source` | `user/system` | 区分系统内置与用户文档 |
| `error_msg` | string/null | 失败原因 |

## 5. 页面与接口依赖矩阵

| 页面 | 主要接口 |
| --- | --- |
| `/auth` | `authApi.register`、`authApi.login`、`authApi.getMe` |
| `/` | `assignmentsApi.list`、`subjectsApi.list` |
| `/student` | `assignmentsApi.list`、`subjectsApi.list`、`classesApi.listMy`、`classesApi.join`、`authApi.getMe` |
| `/create` | `subjectsApi.list`、`assignmentsApi.list`、`documentsApi.list`、`documentsApi.upload`、`assignmentsApi.preview`、`assignmentsApi.fromLessonPlan`、`assignmentsApi.create`、`assignmentsApi.update`、`assignmentsApi.publish`、`assignmentsApi.archive`、`assignmentsApi.unarchive`、`assignmentsApi.delete` |
| `/classes` | `classesApi.listMy`、`classesApi.create`、`classesApi.listMembers`、`classesApi.listGroups`、`classesApi.createGroup`、`classesApi.assignGroupMember`、`classesApi.removeGroupMember`、`classesApi.deleteGroup`、`classesApi.resetInviteCode` |
| `/knowledge` | `documentsApi.list`、`documentsApi.upload`、`documentsApi.delete` |
| `/assignment/:id` 学生态 | `assignmentsApi.getById`、`assignmentsApi.listGroups`、`submissionsApi.listMy`、`submissionsApi.create`、`submissionsApi.update`、`submissionsApi.submit`、`evaluationsApi.listBySubmission` |
| `/assignment/:id` 教师态 | `assignmentsApi.getById`、`assignmentsApi.listGroups`、`classesApi.listMy`、`classesApi.listMembers`、`submissionsApi.listByAssignment`、`assignmentsApi.createGroup`、`assignmentsApi.updateGroupMembers`、`assignmentsApi.deleteGroup`、`evaluationsApi.listBySubmission` |
| `/grading/:submissionId` | `submissionsApi.getById`、`assignmentsApi.getById`、`submissionsApi.listByAssignment`、`assignmentsApi.listGroups`、`evaluationsApi.listBySubmission`、`evaluationsApi.aiAssist`、`evaluationsApi.createTeacher` |

## 6. 接口清单

## 6.1 认证 Auth

| 方法 | 路径 | 鉴权 | 主要页面 |
| --- | --- | --- | --- |
| `POST` | `/api/v2/auth/register` | 否 | `/auth` |
| `POST` | `/api/v2/auth/login` | 否 | `/auth` |
| `GET` | `/api/v2/auth/me` | 是 | App 启动、`/student` 入班后刷新 |

### `POST /api/v2/auth/register`

请求体：

```json
{
  "username": "teacher_001",
  "password": "password123",
  "role": "teacher",
  "name": "张老师",
  "grade": 7,
  "class_name": "1班"
}
```

说明：

- `grade/class_name` 只在学生注册时传
- 前端注册后会立即触发登录

### `POST /api/v2/auth/login`

使用 `application/x-www-form-urlencoded`，字段：

- `username`
- `password`
- `role`

成功响应：

```json
{
  "access_token": "xxx",
  "token_type": "bearer"
}
```

### `GET /api/v2/auth/me`

成功响应需要至少覆盖 `ApiUser` 的关键字段。

## 6.2 学科 Subjects

| 方法 | 路径 | 鉴权 | 主要页面 |
| --- | --- | --- | --- |
| `GET` | `/api/v2/subjects/` | 是 | 仪表盘、设计器、学生页 |
| `GET` | `/api/v2/subjects/{id}` | 是 | 当前 UI 未直接使用 |

查询参数：

- `stage`
- `category`

前端现状：

- 多数页面直接拉全量，再按 `primary_available/middle_available` 过滤

## 6.3 班级与班级小组 Classes

| 方法 | 路径 | 鉴权 | 主要页面 |
| --- | --- | --- | --- |
| `POST` | `/api/v2/classes/` | 是 | `/classes` |
| `GET` | `/api/v2/classes/my` | 是 | `/student`、`/classes`、教师作业详情 |
| `POST` | `/api/v2/classes/join` | 是 | `/student` |
| `GET` | `/api/v2/classes/{classId}/members` | 是 | `/classes`、教师作业详情 |
| `GET` | `/api/v2/classes/{classId}/groups` | 是 | `/classes` |
| `POST` | `/api/v2/classes/{classId}/groups` | 是 | `/classes` |
| `POST` | `/api/v2/classes/{classId}/groups/{groupId}/members` | 是 | `/classes` |
| `DELETE` | `/api/v2/classes/{classId}/groups/{groupId}/members/{studentId}` | 是 | `/classes` |
| `DELETE` | `/api/v2/classes/{classId}/groups/{groupId}` | 是 | `/classes` |
| `POST` | `/api/v2/classes/{classId}/invite-code/reset` | 是 | `/classes` |

重点说明：

- `join` 的请求体是 `{ "invite_code": "ABCD1234" }`
- `listMembers` 返回 `classroom + members + total`
- `assignGroupMember` 只需提交 `student_id`
- 班级页面变更分组后会同时刷新 members 和 groups

## 6.4 作业 Assignments

| 方法 | 路径 | 鉴权 | 主要页面 |
| --- | --- | --- | --- |
| `POST` | `/api/v2/assignments/preview` | 是 | `/create` |
| `POST` | `/api/v2/assignments/from-lesson-plan` | 是 | `/create` |
| `POST` | `/api/v2/assignments/` | 是 | `/create` |
| `GET` | `/api/v2/assignments/` | 是 | 仪表盘、学生页、设计器 |
| `GET` | `/api/v2/assignments/{id}` | 是 | 作业详情、批改页 |
| `PUT` | `/api/v2/assignments/{id}` | 是 | `/create` |
| `POST` | `/api/v2/assignments/{id}/publish` | 是 | `/create` |
| `POST` | `/api/v2/assignments/{id}/archive` | 是 | `/create` |
| `POST` | `/api/v2/assignments/{id}/unarchive` | 是 | `/create` |
| `DELETE` | `/api/v2/assignments/{id}` | 是 | `/create` |
| `POST` | `/api/v2/assignments/{id}/generate-steps` | 是 | 当前 UI 未直接使用 |
| `POST` | `/api/v2/assignments/{id}/groups` | 是 | 教师作业详情 |
| `PUT` | `/api/v2/assignments/{id}/groups/{groupId}/members` | 是 | 教师作业详情 |
| `DELETE` | `/api/v2/assignments/{id}/groups/{groupId}` | 是 | 教师作业详情 |
| `GET` | `/api/v2/assignments/{id}/groups` | 是 | 作业详情、批改页 |

### `GET /api/v2/assignments/`

查询参数：

- `page`
- `page_size`
- `published_only`
- `include_archived`

典型场景：

- 教师仪表盘：`published_only=false, include_archived=true`
- 学生仪表盘：`published_only=true`

### `POST /api/v2/assignments/preview`

用途：

- 让 AI 根据当前表单生成目标、步骤、量规草稿

请求体与 `AssignmentCreatePayload` 一致。

关键响应字段：

- `objectives_json`
- `phases_json`
- `rubric_json`
- `meta`

### `POST /api/v2/assignments/from-lesson-plan`

用途：

- 基于参考文档生成作业草稿

特点：

- 超时时间 `90000ms`
- 前端会把返回结果与当前表单做“补全式合并”

### `PUT /api/v2/assignments/{id}`

当前前端主要更新以下字段：

- `title`
- `topic`
- `description`
- `document_id`
- `deadline`
- `objectives_json`
- `phases_json`
- `rubric_json`

这意味着如果重设计要做更强的“结构化编辑回写”，应先确认后端更新接口是否完整覆盖所有字段。

## 6.5 提交 Submissions

| 方法 | 路径 | 鉴权 | 主要页面 |
| --- | --- | --- | --- |
| `POST` | `/api/v2/submissions/` | 是 | 学生作业详情 |
| `GET` | `/api/v2/submissions/my` | 是 | 学生作业详情 |
| `GET` | `/api/v2/submissions/{id}` | 是 | 批改页 |
| `PUT` | `/api/v2/submissions/{id}` | 是 | 学生作业详情 |
| `POST` | `/api/v2/submissions/{id}/submit` | 是 | 学生作业详情 |
| `DELETE` | `/api/v2/submissions/{id}` | 是 | 当前 UI 未直接使用 |
| `GET` | `/api/v2/submissions/assignment/{assignmentId}` | 是 | 教师作业详情、批改页 |

### `POST /api/v2/submissions/`

典型请求体：

```json
{
  "assignment_id": 101,
  "phase_index": 0,
  "group_id": 12,
  "content_json": {
    "text": ""
  }
}
```

### `PUT /api/v2/submissions/{id}`

当前前端主要更新：

- `content_json`
- `attachments_json`
- `checkpoints_json`

### `POST /api/v2/submissions/{id}/submit`

这是学生主链路里最关键的接口。

前端依赖以下语义：

- 当前 draft 提交后变为 submitted
- 如有下一阶段，响应中可能返回 `next_submission_id`
- 若 `next_submission_id` 存在，前端自动跳转下一阶段

## 6.6 评价 Evaluations

| 方法 | 路径 | 鉴权 | 主要页面 |
| --- | --- | --- | --- |
| `POST` | `/api/v2/evaluations/teacher` | 是 | `/grading/:submissionId` |
| `POST` | `/api/v2/evaluations/self` | 是 | 当前 UI 未直接使用 |
| `POST` | `/api/v2/evaluations/peer` | 是 | 当前 UI 未直接使用 |
| `GET` | `/api/v2/evaluations/submission/{submissionId}` | 是 | 作业详情、批改页 |
| `POST` | `/api/v2/evaluations/ai-assist?submission_id={id}` | 是 | `/grading/:submissionId` |
| `GET` | `/api/v2/evaluations/my-received` | 是 | 当前 UI 未直接使用 |

### `POST /api/v2/evaluations/teacher`

请求体：

```json
{
  "submission_id": 301,
  "score_numeric": 3,
  "dimension_scores_json": {
    "问题分析": 3,
    "成果质量": 4
  },
  "feedback": "建议补充证据链说明。"
}
```

关键约束：

- `score_numeric` 固定为 `1-4`
- `dimension_scores_json` 需与量规维度一致
- `feedback` 必填

### `POST /api/v2/evaluations/ai-assist`

关键响应：

- `suggested_level`
- `suggested_score`
- `dimension_scores`
- `feedback`
- `evidence`

前端当前只消费分数和评语，未直接展示证据数组。

## 6.7 文档 Documents

| 方法 | 路径 | 鉴权 | 主要页面 |
| --- | --- | --- | --- |
| `GET` | `/api/documents` | 是 | `/knowledge`、`/create` |
| `POST` | `/api/documents/upload` | 是 | `/knowledge`、`/create` |
| `GET` | `/api/documents/{id}` | 是 | 当前 UI 未直接使用 |
| `DELETE` | `/api/documents/{id}` | 是 | `/knowledge` |

说明：

- 这组接口不在 `/api/v2` 下
- 上传使用 `FormData`
- 上传成功后响应只返回最小信息：
  - `document_id`
  - `filename`
  - `status/parsing_status`

## 7. 前端校验与后端接口的配合关系

## 7.1 认证

前端会先拦截：

- 空工号/学号
- 账号格式错误
- 密码长度不足
- 学生缺少年级/班级

后端仍应继续兜底校验。

## 7.2 作业设计

前端会先拦截：

- 标题为空
- 主题为空
- 主学科未选
- 年级与学段不匹配
- 融合学科重复或包含主学科
- 发布时步骤数少于 2
- 发布时量规维度少于 2

## 7.3 提交

前端会先拦截：

- 附件 URL 非法
- 正式提交前完全没有证据

## 7.4 教师评分

前端会先拦截：

- 教师评语为空
- 维度与量规不一致
- 分值超出 1-4

## 8. 对重设计实现最重要的接口风险点

以下点在重设计落地前最好和后端再对齐一次：

1. `PUT /assignments/{id}` 的更新能力是否足够支撑更强的结构化编辑。
2. `/api/documents` 是否会长期维持在 `/api/v2` 之外。
3. `Assignment.rubric_json.dimensions[].levels` 是否后续会成为必用字段。
4. `Submission.checkpoints_json` 的真实写入策略，当前学生端主要是读，不是完整编辑。
5. 自评、互评接口虽然存在，但当前前端没有界面，后续是否进入重设计范围。

## 9. 联调最小清单

如果后续要开始重设计后的前端实现，至少需要后端确认以下接口保持可用：

- `POST /api/v2/auth/login`
- `GET /api/v2/auth/me`
- `GET /api/v2/subjects/`
- `GET /api/v2/classes/my`
- `POST /api/v2/classes/join`
- `GET /api/v2/assignments/`
- `GET /api/v2/assignments/{id}`
- `POST /api/v2/assignments/preview`
- `POST /api/v2/assignments/from-lesson-plan`
- `POST /api/v2/submissions/`
- `PUT /api/v2/submissions/{id}`
- `POST /api/v2/submissions/{id}/submit`
- `GET /api/v2/evaluations/submission/{submissionId}`
- `POST /api/v2/evaluations/teacher`
- `POST /api/v2/evaluations/ai-assist`
- `GET /api/documents`
- `POST /api/documents/upload`

## 10. 结论

如果只是做页面框架和视觉方案，上一份需求文档已经够用。

但如果要把重设计后的页面真正做成可运行前端，就必须把这里的接口约束一起带上，尤其是：

- 认证与 `401` 失效处理
- 作业、提交、评分三条主链路的请求顺序
- 文档状态和 AI 接口的异步反馈
- 表单前置校验与后端最终校验的边界

这份文档可以直接作为后续前端实现、联调和接口变更评审的基础说明。
