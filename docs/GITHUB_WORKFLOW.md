# GitHub Workflow

This project uses a two-branch model:
- `main`: production-ready branch
- `develop`: integration branch for active work

## Branch Naming
- Feature work: `feature/<short-name>`
- Bug fixes: `fix/<short-name>`
- Chore/docs: `chore/<short-name>` or `docs/<short-name>`

## Standard Flow
1. Sync local branches:
   - `git checkout develop`
   - `git pull origin develop`
2. Create a work branch from `develop`:
   - `git checkout -b feature/<short-name>`
3. Implement changes and run local checks.
4. Push branch and open PR:
   - target branch: `develop`
5. After review and merge to `develop`, promote tested changes to `main` through a PR from `develop` to `main`.

## Hotfix Flow
1. Branch from `main`:
   - `git checkout main`
   - `git pull origin main`
   - `git checkout -b fix/<short-name>`
2. Apply fix, validate, and open PR to `main`.
3. After merge, open a follow-up PR from `main` back into `develop` to keep branches aligned.

## Required Checks
- Frontend build (`apps/kiosk-frontend`)
- Backend compile smoke (`apps/kiosk-backend`)
- Offline integrity check (`scripts/check_offline_integrity.py`)

