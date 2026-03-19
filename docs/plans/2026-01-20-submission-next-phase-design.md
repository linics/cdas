# 2026-01-20-Submission-Next-Phase-Design

## 背景
学生提交当前阶段后，需要进入后续阶段继续完成作业。目前缺少明确入口，导致流程中断。

## 目标
- 在提交完成后提供“进入下一阶段”入口。
- 若下一阶段草稿已存在，直接跳转到已有草稿。
- 若已是最后阶段，提示并不跳转。

## 方案
- 后端提交接口返回 `next_submission_id`：
  - `submission_mode != ONCE` 且存在下一阶段时，查找已有草稿；不存在则创建并返回新 ID。
  - 若无下一阶段，返回 `null`。
- 前端在 `StudentSubmissionPage` 增加“进入下一阶段”按钮：
  - 仅在 `status === submitted` 且存在下一阶段时显示。
  - 点击后调用提交接口并读取 `next_submission_id` 跳转。

## 数据流
1. 学生提交当前阶段。
2. 后端创建/复用下一阶段草稿并返回 `next_submission_id`。
3. 前端跳转到 `/my-details/{next_submission_id}`。

## 错误处理
- 若接口失败：保留当前状态并提示错误。
- 若 `next_submission_id` 为空：提示“已是最后阶段”。

## 测试建议
- 提交后返回 `next_submission_id`。
- 已有草稿时返回已有 ID。
- 最后阶段返回 `null`。
