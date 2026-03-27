# 2026-03 受控升级范围裁剪

本文件记录本轮“受控工程化升级”的固定边界，避免实现过程中范围持续外溢。

## 本轮必须做

- 收紧 `assignment / submission / evaluation` 的合同与错误语义
- 统一 `preview / from-lesson-plan / ai-assist` 的 fallback 与 `meta` 约定
- 抽离核心前端页面中的重复派生与响应适配逻辑
- 收口共享组件与主题 token 在核心页面的消费
- 补齐最小关键 contract tests、mapper tests、主链路 smoke 与可执行的 API e2e 门禁

## 本轮不做

- 数据库语义迁移或迁移体系重做
- Auth / Classroom 领域重构
- 全站 UI 重写或新设计系统替换
- 新 API 版本
- 新 AI 模型接入、多模型路由或更复杂 RAG 策略
- 扩张 `frontend/src/app/data/*` 遗留本地模型层

## 下轮再评估

- 将 `assignments / submissions / evaluations` 中更多领域逻辑下沉到更稳定的服务或 contracts 层
- 在核心页面彻底摆脱遗留本地模型层后，规划其正式退役
- 若 SQLite 迁移治理继续成为瓶颈，再单独立项处理启动期 `create_all + migration` 的混合策略
