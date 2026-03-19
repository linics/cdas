# CDAS Frontend (Canonical)

## Repository Role

This directory is the canonical frontend source for CDAS integration work.

- Frontend root: `frontend/`
- Backend root: repository root (`app/`, `scripts/`)

## Local Development

### 1) Install dependencies

```bash
npm install
```

Optional environment setup:

```bash
cp .env.example .env
```

Windows PowerShell alternative:

```powershell
Copy-Item .env.example .env
```

### 2) Start frontend

```bash
npm run dev:local
```

Frontend URL: `http://127.0.0.1:5173`

若前后端跨域部署，请在 `frontend/.env` 中设置：

```bash
VITE_API_BASE_URL=https://<your-backend-domain>
```

### 3) Ensure backend is running

Backend URL: `http://127.0.0.1:8000`

Backend `.env` template is available at:

- `.env.example` (repo root)

## Quality Baseline Commands

Run these before handoff:

```bash
npm run check:build
npm run check:api-e2e
```

Or run both:

```bash
npm run check:all
```

## Integration Docs

- Phase plan: `docs/integration/phase-plan.md`
- Verification log: `docs/integration/verification-log.md`
- Normalization plan: `docs/integration/normalization-plan-2weeks.md`
- Repo governance: `docs/integration/repo-governance.md`
- API governance: `docs/integration/api-contract-governance.md`
- Backend quality baseline: `docs/integration/backend-quality-baseline.md`
- 15-minute onboarding: `docs/integration/onboarding-15min.md`
