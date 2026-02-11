# Contributing Guide

Thanks for contributing to `Umrah_Tayyib`.

## Scope and Safety
- Do not change backend API response contracts unless explicitly approved.
- Do not commit secrets, `.env` files, or local machine artifacts.
- Keep changes minimal and targeted.
- For UI work, preserve kiosk constraints (touch-first, no full-page scroll in core flows).

## Branching Model
- Stable: `main`
- Integration: `develop`
- Work branches: `feature/<short-name>`, `fix/<short-name>`, `chore/<short-name>`

## Local Validation Before PR
Frontend:
```powershell
cd apps/kiosk-frontend
npm ci
npm run build
```

Backend:
```powershell
cd ..\kiosk-backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m compileall app
```

Integrity:
```powershell
cd ..\..
python scripts/check_offline_integrity.py
```

## Pull Request Rules
- Open PRs to `develop` unless it is an urgent hotfix.
- Keep PR title clear and specific.
- Include:
  - what changed
  - why it changed
  - how you tested it
  - risk/rollback notes for non-trivial changes

## Commit Messages
Use concise conventional-style messages when possible:
- `feat: ...`
- `fix: ...`
- `chore: ...`
- `docs: ...`

