# 学生进入下一阶段提交设计

## 背景
学生在多阶段作业中提交当前阶段后，系统需要自动准备下一阶段草稿，支持继续提交后续阶段。

## 目标
- 多阶段作业提交后自动创建/复用下一阶段草稿。
- 前端提供“进入下一阶段”按钮，跳转到下一阶段草稿。
- 一次性提交（ONCE）不显示该入口。

## 架构与数据流
1. 学生提交当前阶段：调用 `POST /api/v2/submissions/{id}/submit`。
2. 后端在提交成功后：
   - 若作业为多阶段且存在下一阶段：查找是否已有下一阶段草稿。
   - 若已有：复用；若没有：创建新草稿并返回其 ID。
3. 返回原有响应字段 + `next_submission_id`。
4. 前端若拿到 `next_submission_id`，提示并跳转 `/my-details/{next_submission_id}`。

## 后端设计
- 扩展 `SubmissionResponse` 增加 `next_submission_id: Optional[int]`。
- `submit_submission` 逻辑：
  - 标记当前提交为 `submitted`。
  - 若 `submission_mode != ONCE` 且存在下一阶段：
    - 查询下一阶段草稿（相同 assignment、student、next_phase_index）。
    - 不存在则创建草稿，`flush` 获取 ID。
  - 返回包含 `next_submission_id` 的响应。

## 前端设计
- 学生提交页新增“进入下一阶段”按钮：
  - `submission.status === 'submitted'`
  - `assignment.submission_mode !== 'once'`
  - `assignment.phases_json[submission.phase_index + 1]` 存在
- 点击后调用提交接口，读取 `next_submission_id`：
  - 存在：提示“已为你准备下一阶段草稿”，跳转详情页
  - 为空：提示“已是最后阶段”
- 提示方式使用原生 `alert`，不新增组件。

## 错误处理
- 权限/不存在/已评分等沿用现有错误处理。
- 无下一阶段时 `next_submission_id` 返回 `null`。

## 测试
- 后端单测覆盖：
  - 提交后返回 `next_submission_id`
  - 重复提交返回相同 `next_submission_id`
