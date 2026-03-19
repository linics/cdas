# CDAS 产品设计与规范基线

最后更新：2026-03-19

## 0. 文档定位

本文件是 CDAS 当前版本的规范性产品文档。它描述的是实现必须遵守的业务边界、数据合同和交互约束，而不是仅供参考的说明文字。

实现团队必须同时参考以下文档：

- 本文档：产品目标、角色边界、业务流程、关键合同
- `docs/CONSTRAINT_GOVERNANCE.md`：写入校验、兼容策略、工程治理门
- `frontend/docs/integration/api-contract-governance.md`：`/api/v2` 合同演进规则

## 1. 产品目标

CDAS 面向 K12 跨学科作业场景，必须支持教师完成设计、发布、过程跟踪和评价闭环。

系统必须持续满足以下目标：

1. 降低设计成本：教师可在结构化编辑器中形成作业草稿。
2. 强化过程证据：学生提交必须能够绑定阶段、证据与反馈。
3. 提高评价一致性：教师评分必须锚定统一量规和证据。
4. 保持教师决策权：AI 只能辅助，不得自动发布或自动终评。

非目标：

- 不建设完整 LMS。
- 不把 AI 输出当作最终教学决定。
- 不支持未审阅的自动化批量发布。

## 2. 角色与权限

### 2.1 教师

教师 MUST 能够：

- 创建、编辑、发布、归档作业
- 上传参考资料和教案，触发 AI 生成
- 查看提交、评分并给出反馈
- 管理班级、小组与邀请码

### 2.2 学生

学生 MUST 只能：

- 查看已发布且对自己可见的作业
- 创建草稿、阶段提交、查看反馈
- 加入班级并参与作业小组

### 2.3 权限原则

- 学生 MUST NOT 访问教师管理接口。
- 学生 MUST NOT 查看他人的个人提交；小组提交仅限同组成员可见。
- 教师 MUST 只能操作自己创建的作业、班级与评价数据。
- 关键写操作 SHOULD 保留时间与操作者信息。

## 3. 核心流程

### 3.1 作业设计

教师设计作业时，系统 MUST 支持以下输入：

- 标题、主题、学段、年级、主学科、融合学科
- 作业类型、探究深度、提交模式、作业周期
- 目标（knowledge/process/emotion）
- 阶段与步骤
- 评价量规

系统 MUST 提供两条生成链路：

- `AI 预览`：基于教师表单上下文生成草稿
- `从教案一键生成`：基于已入库教案生成草稿

AI 生成结果 MUST 可编辑，且默认仅形成草稿，不得直接发布。

### 3.2 发布与组织

教师发布前，系统 MUST 校验：

- 作业结构完整
- 步骤与 checkpoint 可核验
- 量规维度数量满足最低要求
- 学段、年级、学科配置有效

发布后，教师 SHOULD 能继续查看提交、评分与归档，但 MUST NOT 修改已经提交后依赖的核心结构以造成含义漂移。

### 3.3 学生提交

学生提交 MUST 绑定到具体作业和阶段。

- 草稿允许多次保存
- 正式提交前 MUST 至少包含一项证据：文本、附件或已完成 checkpoint
- 附件链接 MUST 为有效 `http/https` URL
- `phase_index` / `step_index` MUST 与当前作业结构一致

### 3.4 教师评价

教师评价 MUST 满足：

- `score_numeric` 固定为 1-4
- 维度分数 MUST 与 rubric 维度严格一致
- 反馈文本 MUST 非空
- AI 建议只能作为建议，不得覆盖教师最终确认

## 4. 知识库与 RAG

### 4.1 文档输入

系统 MUST 支持 `PDF` / `DOCX` 输入。

- 文档在状态为 `READY` 前 MUST NOT 参与生成链路
- 向量库和上传文件属于运行时产物，MUST NOT 进入版本库
- 重建索引 SHOULD 通过脚本执行，不依赖手工目录操作

### 4.2 生成链路约束

- `AI 预览` 和 `教案一键生成` MUST 返回结构化 JSON
- 生成链路 SHOULD 返回 `meta.source/prompt_version/used_rag/fallback_reason`
- 外部模型失败时 MUST 回退到可编辑默认草稿，不能让流程中断

## 5. 数据合同

### 5.1 Assignment

`assignment` 写入合同 MUST 满足：

- `title/topic` 去首尾空格后不能为空
- `grade` 必须与 `school_stage` 匹配
- `main_subject_id` 必填且存在
- `related_subject_ids` 必须去重，且不得包含主学科
- `assignment_type` 与子类型字段必须一致，不允许互斥组合
- 发布时至少需要 2 个步骤、2 个量规维度
- 草稿创建 SHOULD 使用本地默认结构补齐，不得强依赖外部 AI 成功返回

### 5.2 Submission

`submission` 写入合同 MUST 满足：

- `phase_index` / `step_index` 落在 assignment 范围内
- `checkpoints_json` 只能引用 assignment 已定义的 checkpoint
- 正式提交时至少有一项证据
- 小组提交必须验证小组归属与成员身份

### 5.3 Evaluation

`evaluation` 写入合同 MUST 满足：

- 教师评分为 1-4 四档
- 对显式 rubric，`dimension_scores_json` 与 rubric 维度完全对齐
- 对系统补齐的默认占位 rubric，教师评分 MAY 保持旧兼容输入
- `feedback` 非空
- 证据不足时 SHOULD 通过反馈说明，而不是静默给高分

### 5.4 Auth

认证合同 MUST 满足：

- 注册用户名为 4-32 位字母、数字、下划线或连字符
- 密码至少 8 位
- 学生注册 MUST 提供年级
- `CDAS_AUTH_SECRET_KEY` 为必需环境变量
- 密码哈希 MUST 使用 `bcrypt`

## 6. 前端交互基线

- 设计页、提交页、评分页、注册页 MUST 在前端先做输入拦截，不只依赖后端报错。
- 草稿保存可以比正式发布/提交更宽松，但发布/提交 MUST 走完整校验。
- 错误提示 SHOULD 指向具体字段或具体业务约束，不能只提示“保存失败”。
- 前端 MUST 兼容读取旧数据，但重新编辑保存时应输出新规范结构。

## 7. 工程治理

### 7.1 质量门

后端 MUST 通过：

- `python scripts/check_contract_docs_sync.py`
- `python scripts/check_backend_quality.py`

前端 MUST 通过：

- `npm run check:lint`
- `npm run check:typecheck`
- `npm run check:test`
- `npm run check:build`

如接口行为变更，还 SHOULD 执行：

- `npm run check:api-e2e`

### 7.2 代码组织

- 路由文件 SHOULD 只保留 HTTP 语义和编排逻辑
- 合同模型 SHOULD 放到 `app/contracts/`
- 页面级校验 SHOULD 放到 `frontend/src/app/validation/`
- 新约束 MUST 有测试覆盖，不能只写文档

## 8. 部署与运行约束

- 受支持 Python 基线为 `3.12`
- `.env` MUST NOT 入库
- 生产环境 MUST 使用持久化数据库和持久化 `storage/`
- SQLite 仅适用于单机/低并发环境
- 任何泄露的密钥 MUST 立即轮换

## 9. 兼容策略

本轮约束增强采用兼容过渡：

- 读接口保持兼容，旧数据可继续读取
- 写接口开始拒绝不符合新合同的输入
- 旧数据重新编辑保存时，应被规范化为新结构
- 破坏性变更需要先写迁移说明，再进入实现
