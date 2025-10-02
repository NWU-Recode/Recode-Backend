# Contributing to Recode

We keep it simple. Follow these rules and we’ll ship faster:

## 1. Branching
- `main` = production only.
- `dev` = staging branch.
- Feature work → `feature/<name>`.
- Always PR into `dev`. Never commit straight to `main`.

## 2. Commits
- Keep them small, focused.
- Use clear messages: `fix:`, `feat:`, `chore:`, `docs:`.

## 3. Pull Requests
- PRs must be reviewed before merge.
- Write a short description of what/why, not just “fixed stuff”.
- If it breaks tests, it doesn’t ship.

## 4. Code Style
- Backend: Python (FastAPI, Pydantic). Stick to type hints.
- Frontend: React + TS + Tailwind. Keep it clean, no inline mess.
- Follow existing patterns. Don’t reinvent.

## 5. Issues
- Check open issues before creating new ones.
- Link commits/PRs to issues.

## 6. Environment
- `.env.example` has what you need. Don’t commit secrets.
- Run migrations before testing.

---

### Golden Rule
Respect the flow. Small, clean, reviewed code beats big, messy drops.
