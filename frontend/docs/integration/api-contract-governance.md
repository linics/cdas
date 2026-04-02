# API Contract Governance (`/api/v2`)

最后更新：2026-03-19

## Purpose

定义 `frontend` 消费的 `/api/v2` 合同演进规则，确保产品约束、后端实现和前端消费保持一致。

## Stability Policy

- `/api/v2` 被视为稳定合同。
- 默认策略是读兼容、写收紧。
- 破坏性变更必须先给出迁移说明，再合入实现。

## Contract Rules

- JSON 字段命名保持 `snake_case`
- 现有 `id` 字段含义稳定，不可重命名
- 日期时间使用 ISO 8601 字符串
- 现有 enum 值不得原位改名
- 现有成功响应字段不得直接删除或改类型
- 对既有成功字段只允许新增可选子字段，例如 `attachments_json[]` 的扩展元数据

## Write-Side Constraint Policy

以下变化允许在不破坏成功响应的前提下逐步收紧：

- 对无效写入增加 `400/422`
- 对注册、作业发布、正式提交、教师评分增加更严格校验
- 对无效附件 URL、非法维度、非法阶段索引、缺失证据直接拒绝
- 草稿创建默认不得依赖外部 AI 才能成功

新增写侧约束时必须满足：

1. 同步更新 `docs/PRODUCT_DESIGN.md` 或 `docs/CONSTRAINT_GOVERNANCE.md`
2. 增加对应后端反例测试
3. 增加前端校验或错误提示
4. 保留 `detail` 作为主要错误消息字段

## Compatibility Expectations For Frontend

前端必须：

- 容忍新增的可选响应字段
- 对旧数据提供 defensive defaults
- 对新增 `400/422` 提示展示 `detail`
- 在保存前将旧结构归一化为当前写入合同
- 对 `from-lesson-plan` 请求采用“仅发送教师已手动修改的顶层约束”语义；未发送字段视为允许后端按教案重新推断；已发送字段可包含标题、主题、说明、背景、作业类型及子类型等
- 对历史默认占位 rubric 保持评分兼容；对显式 rubric 按严格维度对齐处理
- 对 AI 响应中的新增可选 `meta` 字段采用 defensive defaults，不将其视为必填
- 对 `preview`、`from-lesson-plan`、`ai-assist` 的 `meta.source/prompt_id/prompt_version/used_rag/fallback_reason` 做向后兼容消费
- 对 `from-lesson-plan` 等链路中的 `meta.input_truncated` 与 lesson plan warning 做语义兼容消费：它们表示模型输入在进入推理前发生过压缩或截断，而不是仅表示最后一次字符串截断函数命中
- 对 `SubmissionResponse.attachments_json[]` 中新增的 `attachment_id/source/parsing_status/mime_type/error_msg/summary_text` 采用可选字段消费，不把它们当作写入必填项
- 前端文档与附件上传入口统一按 `PDF / DOCX / TXT` 约束做前置校验，不再提示或接受 `.doc`

## Required Checks

API 合同相关改动必须至少通过：

- `python scripts/check_contract_docs_sync.py`
- `python scripts/check_backend_quality.py`
- `npm run check:lint`
- `npm run check:typecheck`
- `npm run check:test`
- `npm run check:build`

如请求/响应行为发生变化，还应执行：

- `npm run check:api-e2e`
