# ICHS Umrah AI Search Kiosk

Monorepo for the kiosk frontend and backend.

## Repo Layout
- `apps/kiosk-frontend` - React + Vite + TypeScript + Tailwind
- `apps/kiosk-backend` - FastAPI + Uvicorn
- `data/offline_pack` - offline answer pack
- `data/rag_corpus` - approved corpus and source registry
- `data/chroma_index` - local Chroma index
- `assets` - branding and Tayyib media assets
- `scripts` - ingestion and validation utilities

## Environment Files
- Root `.env.example` - shared local defaults.
- Root `.env` - optional shared local values.
- `apps/kiosk-frontend/.env.example` - frontend vars (`VITE_API_BASE_URL`).
- `apps/kiosk-backend/.env.example` - backend vars (OpenAI, DB, Chroma, runtime mode).
- `apps/kiosk-backend/.env` - backend local overrides (not committed with secrets).

Required backend variables:
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (default `gpt-4o`)
- `OPENAI_EMBED_MODEL` (default `text-embedding-3-large`)
- `ALLOWED_ORIGINS` (for frontend dev URL)

Important optional runtime flags:
- `KIOSK_DEV_MODE=1` enables `/api/diag`
- `EVENT_MODE=true` reduces verbose logging and disables dev-only behavior
- `CHROMA_TELEMETRY=false` disables Chroma telemetry

## Local Development
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

URLs:
- Frontend: `http://localhost:5175`
- Backend health: `http://127.0.0.1:8005/api/health`
- RAG test: `http://127.0.0.1:8005/api/rag_test`
- Version: `http://127.0.0.1:8005/api/version`

Optional one-command launcher:
```powershell
powershell -NoExit -ExecutionPolicy Bypass -File .\dev.ps1
```

## Offline Pack Integrity
Validate that every offline entry has valid `source_ids`:
```powershell
python scripts/check_offline_integrity.py
```

## RAG Ingestion
Run from repo root:
```powershell
python scripts/ingest_sources.py --reset --max-sources 1 --max-pages 5
```

Useful flags:
- `--max-sources`
- `--max-pages`
- `--chunk-chars`
- `--overlap-chars`
- `--batch-size`
- `--cache-dir`
- `--refresh`
- `--reset`
- `--reset-cache`

## UI and Event Readiness Checks
```powershell
python .agents/skills/kiosk-ui-qa/scripts/run_checks.py
python .agents/skills/event-readiness-checklist/scripts/run_checklist.py
```

## Security Notes
- Runtime question text is never stored raw in analytics (hashed only).
- Frontend runtime audit should use `npm audit --omit=dev` for production surface.

## Release Gates
CI workflow runs:
- frontend lint + build
- backend import smoke check
- offline pack integrity check
- kiosk UI QA check
