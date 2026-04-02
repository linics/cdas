# CDAS 约束治理总表

最后更新：2026-03-19

本文档是 CDAS 当前版本的单一约束源，覆盖写入合同、错误语义、兼容过渡和工程治理要求。所有涉及 `assignment / submission / evaluation / classroom / auth` 的修改，都必须同步检查本文件。

## 1. 写入合同

### 1.1 Assignment

| 字段 | 规则 | 强制级别 |
| --- | --- | --- |
| `title` | trim 后不能为空 | MUST |
| `topic` | trim 后不能为空 | MUST |
| `school_stage + grade` | `primary -> 1-6`，`middle -> 7-9` | MUST |
| `main_subject_id` | 必填且存在 | MUST |
| `related_subject_ids` | 去重，不含主学科，引用必须存在 | MUST |
| `assignment_type` | 与子类型字段一致 | MUST |
| `phases_json` | 发布前总步骤数至少 2 | MUST |
| `checkpoint` | 发布前每个步骤至少 1 个 | MUST |
| `rubric_json.dimensions` | 发布前至少 2 个，名称唯一 | MUST |
| 草稿创建 | 默认使用本地模板补齐，不依赖外部 AI 成功返回 | SHOULD |

说明：

- 草稿创建允许结构逐步完善，但一旦进入发布动作，必须满足完整校验。
- 旧数据可读取，但重新保存时必须输出规范结构。

### 1.2 Submission

| 字段 | 规则 | 强制级别 |
| --- | --- | --- |
| `phase_index` | 必须在 assignment 阶段范围内 | MUST |
| `step_index` | 若提供，必须在阶段步骤范围内 | MUST |
| `attachments_json[].url` | 仅允许 `http/https` | MUST |
| 文件附件 | 通过独立附件域上传，首版仅支持 `PDF/DOCX/TXT` | MUST |
| 文件附件状态 | 存在文件附件时，正式提交前必须全部为 `READY` | MUST |
| 截止后附件清理 | 若晚提交仍允许，学生可删除阻塞正式提交的未就绪文件附件；已 `READY` 的文件附件仍按截止时间限制 | MUST |
| `checkpoints_json` | key 必须存在于 assignment 定义中 | MUST |
| 正式提交 | 至少一项证据：文本 / 附件 / checkpoint | MUST |
| 小组提交 | 必须校验作业归属和成员身份 | MUST |

### 1.3 Evaluation

| 字段 | 规则 | 强制级别 |
| --- | --- | --- |
| `score_numeric` | 1-4 | MUST |
| `dimension_scores_json` | 对显式 rubric，key 与 rubric 完全一致 | MUST |
| `feedback` | trim 后不能为空 | MUST |
| AI 建议 | 仅建议，不得绕过教师确认 | MUST |

### 1.4 Classroom

| 字段 | 规则 | 强制级别 |
| --- | --- | --- |
| `classroom.name` | trim 后不能为空，长度 <= 100 | MUST |
| `group.name` | trim 后不能为空，班级内不重复 | MUST |
| `invite_code` | 4-16 位大写字母/数字（排除易混淆字符） | MUST |

### 1.5 Auth

| 字段 | 规则 | 强制级别 |
| --- | --- | --- |
| `username` | 4-32 位字母、数字、下划线或连字符 | MUST |
| `password` | 至少 8 位 | MUST |
| 学生注册 | 必须提供 `grade` | MUST |
| `CDAS_AUTH_SECRET_KEY` | 启动必需 | MUST |
| 密码哈希 | `bcrypt` | MUST |

## 2. 错误语义

- `400`：业务约束不满足，如学段年级不匹配、维度不一致、证据缺失
- `401`：认证缺失或 token 无效
- `403`：身份存在但无操作权限
- `404`：目标资源不存在
- `422`：请求体结构不符合 Pydantic 合同
- `500`：未预期服务端异常

错误响应必须保留 FastAPI 默认 `detail` 字段；统一异常兜底也必须返回 JSON `detail`。

## 3. 兼容过渡

当前版本采用“读兼容、写收紧”：

- 读接口继续兼容旧结构
- 写接口拒绝不符合新合同的输入
- 前端编辑旧数据时，在保存前归一化为新结构
- 新规则不得悄悄改变现有成功响应字段名
- 历史作业若仅使用系统默认占位 rubric，教师评分保留旧兼容输入；显式 rubric 则按严格维度匹配执行
- AI 链路允许新增可选 `meta` 字段，但不得删除既有成功字段或将可选元数据改成必填

## 4. 前端约束映射

前端必须至少在以下页面提前阻断输入：

- `AssignmentDesigner`：标题、主题、学段年级、步骤、量规、主副学科
- `AssignmentDetail`：附件链接、文件附件状态、正式提交证据、小组名
- `GradingPanel`：反馈必填、维度分数与 rubric 对齐
- `Auth`：用户名/密码/学生年级
- `TeacherClassManager` / `StudentDashboard`：班级名、小组名、邀请码
- `KnowledgeBase`：文件类型和大小

## 5. 工程治理门

### 5.1 必跑检查

- 后端：`python scripts/check_contract_docs_sync.py`、`python scripts/check_backend_quality.py`
- 前端：`npm run check:lint`、`npm run check:typecheck`、`npm run check:test`、`npm run check:build`

### 5.2 文档同步要求

只要修改以下任一文件：

- `app/contracts/*`
- `app/api/v2/auth.py`
- `app/api/v2/assignments.py`
- `app/api/v2/submissions.py`
- `app/api/v2/evaluations.py`
- `app/config.py`

就必须同时更新以下文档中的至少一份：

- `docs/PRODUCT_DESIGN.md`
- `docs/CONSTRAINT_GOVERNANCE.md`
- `frontend/docs/integration/api-contract-governance.md`
- `README.md`

## 6. 实现默认值

除非有明确迁移说明，否则默认遵循以下规则：

- 新增字段只做非破坏性扩展
- 旧字段不改名、不改类型
- `POST /api/v2/assignments/from-lesson-plan` 请求允许新增可选顶层约束字段，用于传递教师已手动修改的字段
- 对 `POST /api/v2/assignments/from-lesson-plan`，未发送字段表示允许重新推断；显式空字符串表示教师清空文本约束；`main_subject_id: null` 表示取消教师覆盖并重新推断主学科
- `SubmissionResponse.attachments_json` 允许新增可选字段，但不得删除原有 `filename/url/type/size_bytes`
- 旧数据读取时允许缺省，但重写时必须归一化
- 生产基线 Python 为 `3.12`
