# CDAS（Cross-Disciplinary Assignment System）

CDAS 是一套面向 K12 场景的跨学科作业系统，支持教师端作业设计、教案一键生成、过程性提交、教师评价与知识库（RAG）辅助生成。

## 文档入口

开始前建议先看两份规范文档：

- [产品设计与规范基线](docs/PRODUCT_DESIGN.md)
- [约束治理总表](docs/CONSTRAINT_GOVERNANCE.md)

接口演进规则见：

- [API Contract Governance](frontend/docs/integration/api-contract-governance.md)
- [2026-03 升级范围裁剪](docs/UPGRADE_SCOPE_2026-03.md)

## 快速启动

### 1. 后端

推荐使用 Python `3.12`：

```bash
python3.12 -m venv .venv312
source .venv312/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

后端地址：`http://127.0.0.1:8000`  
Swagger：`http://127.0.0.1:8000/docs`

### 2. 前端

```bash
cd frontend
npm install
npm run dev:local
```

前端地址：`http://127.0.0.1:5173`

### 3. Worktree 自动初始化

首次在仓库中启用版本化 Git hook：

```bash
bash scripts/install_worktree_hook.sh
```

启用后，执行 `git worktree add ...` 创建新工作树时，会自动运行：

- `scripts/bootstrap_worktree_env.sh`
- 若 `.env` 不存在，则从 `.env.example` 生成
- 若 `frontend/.env.local` 不存在，则写入本地开发默认值
- 创建 `storage/`、`storage/documents/`、`storage/chroma/`
- 修复或创建 `.venv312`，并安装 `requirements.txt`
- 若 `frontend/node_modules` 缺失，则执行 `npm install`

脚本是幂等的，可手动重复运行：

```bash
bash scripts/bootstrap_worktree_env.sh
```

## 环境变量

建议在项目根目录配置 `.env`。至少需要：

- `CDAS_DATABASE_URL`
- `CDAS_DOCUMENTS_DIR`
- `CDAS_CHROMA_PERSIST_DIR`
- `CDAS_AI_LOGS_DIR`
- `CDAS_AUTH_SECRET_KEY`
- `CDAS_CORS_ALLOWED_ORIGINS`

可选 AI 配置：

- `CDAS_DEEPSEEK_API_KEY`
- `CDAS_DEEPSEEK_MODEL`
- `CDAS_SILICONFLOW_API_KEY`
- `CDAS_SILICONFLOW_EMBEDDING_MODEL`
- `CDAS_SILICONFLOW_RERANK_MODEL`

未配置 AI Key 时，核心业务流程仍可运行，但 AI 生成功能会降级。

## 质量门

### 后端

```bash
source .venv312/bin/activate
python scripts/check_contract_docs_sync.py
python scripts/check_backend_quality.py
```

### 前端

```bash
cd frontend
npm run check:lint
npm run check:typecheck
npm run check:test
npm run check:build
```

### 集成联调

```bash
cd frontend
npm run check:api-e2e
```

## Demo 数据准备

如需准备教师评审 demo：

```bash
source .venv312/bin/activate
python scripts/prepare_demo_data.py
```

录制说明见：

- [DEMO_RECORDING_GUIDE.md](docs/DEMO_RECORDING_GUIDE.md)

## 部署注意事项

- Python 生产基线为 `3.12`
- `CDAS_AUTH_SECRET_KEY` 为启动必需项
- SQLite 仅适用于单机/低并发环境
- 生产环境必须持久化 `storage/`
- `.env`、运行时产物、日志不得入库
