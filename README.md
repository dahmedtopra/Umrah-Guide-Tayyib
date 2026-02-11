# ICHS Umrah AI Search Kiosk

Production-oriented kiosk monorepo for Umrah guidance.

## Stack
- Frontend: React + Vite + TypeScript + TailwindCSS
- Backend: FastAPI + Uvicorn (Python 3.11)
- Retrieval: local Chroma index
- Analytics: local SQLite
- Models: OpenAI Responses (`gpt-4o`) and embeddings (`text-embedding-3-large`)

## Repository Structure
- `apps/kiosk-frontend` frontend app
- `apps/kiosk-backend` backend API
- `data/offline_pack` offline Q&A dataset
- `data/rag_corpus` approved source registry and corpus files
- `data/chroma_index` local vector index (generated, not committed)
- `assets` branding and avatar media
- `scripts` ingestion and integrity checks
- `docs` product and workflow documentation

## Prerequisites
- Node.js 20+
- Python 3.11+

## Local Setup (Windows PowerShell)
Backend:
```powershell
cd apps/kiosk-backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8005 --env-file ..\..\.env
```

Frontend:
```powershell
cd apps/kiosk-frontend
npm install
npm run dev -- --port 5175
```

Endpoints:
- Frontend: `http://localhost:5175`
- Health: `http://127.0.0.1:8005/api/health`
- RAG test: `http://127.0.0.1:8005/api/rag_test`
- Version: `http://127.0.0.1:8005/api/version`

## Environment Files
- Root `.env.example`: shared defaults template
- Root `.env`: local secrets and overrides (ignored)
- `apps/kiosk-frontend/.env.example`: frontend env template
- `apps/kiosk-backend/.env.example`: backend env template
- `apps/kiosk-backend/.env`: optional backend-local overrides (ignored)

Core backend variables:
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (default `gpt-4o`)
- `OPENAI_EMBED_MODEL` (default `text-embedding-3-large`)
- `ALLOWED_ORIGINS` (CSV)

Optional runtime flags:
- `KIOSK_DEV_MODE=1` enables dev diagnostics endpoints
- `EVENT_MODE=true` reduces verbose runtime logging
- `CHROMA_TELEMETRY=false` disables Chroma telemetry

## Checks
Offline source integrity:
```powershell
python scripts/check_offline_integrity.py
```

Frontend build:
```powershell
cd apps/kiosk-frontend
npm run build
```

Backend compile smoke:
```powershell
python -m compileall apps/kiosk-backend/app
```

## CI
GitHub Actions runs:
- Frontend install + build
- Backend dependency install + compile smoke
- Offline integrity check

## Security Notes
- No raw user query text is persisted in analytics.
- Keep all `.env` files private and never commit API keys.

## Collaboration
- Branch strategy and team workflow: `docs/GITHUB_WORKFLOW.md`
- Contribution process: `CONTRIBUTING.md`
