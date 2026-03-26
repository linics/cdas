# AGENTS.md

本文件适用于仓库根目录及其所有子目录。若子目录后续出现更细粒度的 `AGENTS.md`，以更近层级文件为准。

## 1. 项目事实

- 项目名：`CDAS`（Cross-Disciplinary Assignment System），面向 K12 跨学科作业场景。
- 后端：Python `3.12`、FastAPI、Pydantic v2、SQLAlchemy，代码位于 `app/`。
- 前端：Vite、React 18、TypeScript，代码位于 `frontend/`。
- 默认数据库：SQLite；结构演进依赖 `migrations/sql/*.sql` 的版本化迁移。
- 运行时目录：`storage/`、`.env`、`frontend/.env.local`、日志与向量库目录都属于运行时产物，不得提交。

## 2. 先读这些文档

凡是涉及业务规则、接口合同、发布/提交/评分约束，先读以下文档，再动代码：

1. `docs/PRODUCT_DESIGN.md`
2. `docs/CONSTRAINT_GOVERNANCE.md`
3. `frontend/docs/integration/api-contract-governance.md`
4. `README.md`

这几个文件在本仓库里是规范性文档，不是“参考资料”。

## 3. 目录职责

### 后端

- `app/api/v2/`: 仅放 HTTP 层、鉴权、参数编排、响应组装。不要把大量规范化逻辑塞进路由。
- `app/contracts/`: Pydantic 写入/读取合同、字段归一化、请求响应模型。接口合同优先放这里。
- `app/models/`: SQLAlchemy 模型与枚举；不要把接口层约束直接硬编码到模型字段注释里当完成。
- `app/services/`: 外部依赖与领域服务，如 AI、库存、RAG 能力。外部服务失败时必须可降级。
- `app/prompts/`: Prompt 模板、注册与加载逻辑；改 AI 生成链路时同步检查这里。
- `app/migrations.py` + `migrations/sql/`: SQLite 迁移入口与 SQL 文件。结构变更不能只改 ORM 模型。

### 前端

- `frontend/` 是唯一规范前端目录，不要在仓库其他位置新建平行前端实现。
- `frontend/src/app/pages/`: 页面级容器与流程编排。
- `frontend/src/app/components/`: 可复用 UI 组件。
- `frontend/src/app/validation/`: 前端输入校验，必须镜像关键写侧约束。
- `frontend/src/app/lib/api.ts`: API client、共享响应类型、错误处理；接口字段变化先看这里。
- `frontend/src/app/lib/mappers.ts`: 前后端结构映射；响应结构调整时同步检查。

### 测试与脚本

- `tests/`: 后端契约、迁移、约束、集成测试。
- `scripts/check_contract_docs_sync.py`: 约束/合同改动后的文档联动门禁。
- `scripts/check_backend_quality.py`: 后端基线门禁。
- `frontend/scripts/run_api_e2e.py`: 前后端联调脚本。

## 4. 必须遵守的产品与合同约束

- `/api/v2` 视为稳定合同，默认策略是“读兼容、写收紧”。
- JSON 字段命名保持 `snake_case`。
- 现有成功响应字段不得随意删除、重命名或改类型。
- 现有 `id` 字段语义保持稳定；现有 enum 值不得原位改名。
- 日期时间保持 ISO 8601 字符串语义。
- 错误语义遵循现有约定：`400/401/403/404/422/500`，错误响应保留 FastAPI `detail` 字段。
- 用户可见业务提示、校验文案、后端 `detail` 文案以中文为主，新增文案应保持现有风格并尽量指向具体字段或约束。
- AI 只能辅助，不能绕过教师确认直接发布、直接终评。
- AI / RAG / 外部模型失败时，核心流程必须降级到本地默认结构或可编辑草稿，不能把教师主流程卡死。

## 5. 变更联动规则

### 写侧约束变更

凡是新增或收紧以下约束之一：注册、作业创建/发布、正式提交、教师评分、班级/小组规则，必须同时完成：

1. 后端写侧校验落地。
2. 对应后端反例测试或契约测试。
3. 前端 `frontend/src/app/validation/` 的前置拦截或错误提示。
4. 至少一份规范文档更新。

### 合同文件变更

如果改动了以下任一文件：

- `app/contracts/*`
- `app/api/v2/auth.py`
- `app/api/v2/assignments.py`
- `app/api/v2/submissions.py`
- `app/api/v2/evaluations.py`
- `app/config.py`

则必须同步更新以下文档中的至少一份，否则 `scripts/check_contract_docs_sync.py` 会失败：

- `docs/PRODUCT_DESIGN.md`
- `docs/CONSTRAINT_GOVERNANCE.md`
- `frontend/docs/integration/api-contract-governance.md`
- `README.md`

### 数据库结构变更

- 任何持久化 schema 变化，都要新增 `migrations/sql/NNN_*.sql`。
- 不要只改 `app/models/*` 然后依赖 `Base.metadata.create_all()` 冒充迁移完成。
- 新迁移要保证 SQLite 可执行，并补至少一个迁移相关测试。
- 保持对历史数据的读取兼容；旧数据重写时再归一化到新结构。

### API 响应或前端消费结构变更

如果改动 `/api/v2` 的请求或响应：

1. 更新 `app/contracts/`。
2. 更新 `frontend/src/app/lib/api.ts` 中的类型或请求封装。
3. 如有映射逻辑，更新 `frontend/src/app/lib/mappers.ts`。
4. 如影响页面交互，更新页面与校验测试。
5. 如属公开合同变化，补文档。

## 6. 代码风格与实现边界

- 优先小步改动，避免无关重构。
- 不要做大规模格式化或 import 排序噪音提交；仓库没有统一 formatter，保持现有文件风格。
- 前端 `frontend/src/app/lib/**/*` 和 `frontend/src/app/validation/**/*` 受更严格 ESLint 约束：
  - 避免 `any`
  - 优先 `import type`
- 新增页面级输入约束时，优先放在 `frontend/src/app/validation/`，不要把复杂校验散落到页面 JSX 中。
- 路由层保留编排职责；复用或抽取复杂规则到 `contracts/`、`services/`、工具函数或前端 validation。
- 不要引入新的“备用前端”“临时 API 版本”或并行数据模型，除非先写迁移说明并更新治理文档。

## 7. 测试与验证

### 本地环境

- Python 基线：`3.12`
- 推荐虚拟环境：`.venv312`
- 前端推荐 Node：CI 使用 `20`
- 首次或新 worktree 环境准备优先使用：

```bash
bash scripts/bootstrap_worktree_env.sh
```

### 提交前至少执行

后端改动：

```bash
source .venv312/bin/activate
python scripts/check_contract_docs_sync.py
python scripts/check_backend_quality.py
```

前端改动：

```bash
cd frontend
npm run check:lint
npm run check:typecheck
npm run check:test
npm run check:build
```

接口行为、前后端联调或消费结构变化：

```bash
cd frontend
npm run check:api-e2e
```

允许先跑针对性测试加快迭代，但最终交付前必须回到对应质量门。

## 8. 领域特定提醒

- 作业、提交、评分、班级、认证都属于强约束域，优先补反例测试，不要只测 happy path。
- 发布前完整性、正式提交证据、评分维度精确匹配这类规则，前后端都必须阻断。
- 旧版兼容仍然存在：`/api` 下文档接口和读取旧数据的能力不要轻易删除。
- `CDAS_AUTH_SECRET_KEY` 是启动必需项；不要通过放宽配置校验来“修复”测试。
- 测试默认使用内存 SQLite；若你的改动依赖持久化 schema 行为，补迁移测试而不是绕过测试环境。

## 9. Agent 工作方式

- 开始改动前，先读相邻实现、相邻测试和相关规范文档。
- 做合同相关改动时，把“后端约束、前端校验、测试、文档”视为一个变更包。
- 生成或修改用户可见文案时，优先复用仓库中已有术语，如“发布前”“正式提交”“评价维度”“反馈”“证据”。
- 若发现需求会触发破坏性变更，先写迁移/兼容方案，再进入实现；不要直接硬改稳定合同。

