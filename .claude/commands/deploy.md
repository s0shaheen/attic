---
description: Deploy to production. Runs a checklist, then deploys frontend (Vercel) and/or backend (Render).
argument-hint: "[--frontend-only] [--backend-only] [--dry-run]"
---

## Pre-deployment checklist

Run ALL of these before deploying. If any fail, stop and fix.

### 1. Tests pass
```bash
cd src/backend && ../../.venv/bin/pytest tests/ -x --tb=short -q 2>&1 | tail -3
cd src/frontend && npm run typecheck 2>&1 | tail -3
cd src/frontend && npm run build 2>&1 | tail -3
```

### 2. On main branch with clean state
```bash
BRANCH=$(git branch --show-current)
[ "$BRANCH" != "main" ] && echo "WARNING: Not on main branch (on $BRANCH)"

UNCOMMITTED=$(git status --porcelain | wc -l | tr -d ' ')
[ "$UNCOMMITTED" != "0" ] && echo "WARNING: $UNCOMMITTED uncommitted files"
```

### 3. Main is up to date
```bash
git fetch origin main
BEHIND=$(git rev-list --count HEAD..origin/main)
[ "$BEHIND" != "0" ] && echo "WARNING: Local main is $BEHIND commits behind origin"
```

### 4. No secrets in committed code
```bash
git log origin/main..HEAD -p | grep -inE '(sk-[a-zA-Z0-9]{20,}|sk_live_|AIza[a-zA-Z0-9]{30,})' || echo "Clean"
```

### 5. Environment check
Verify production environment variables are documented:
```bash
[ -f "docs/setup/production.md" ] || echo "WARNING: No production setup docs"
```

## Deployment

If `--dry-run`: print what would happen and stop.

### Frontend (Vercel)
```bash
# Vercel deploys automatically from main via Git integration
# If not connected yet:
echo "Frontend deploys automatically when you push to main."
echo "If Vercel isn't connected: https://vercel.com/new → Import Git Repository"
echo ""
echo "Manual trigger:"
echo "  npx vercel --prod (from src/frontend/)"
```

### Backend (Render)
```bash
# Render deploys automatically from main via Git integration
# If not connected yet:
echo "Backend deploys automatically when you push to main."
echo "If Render isn't connected: https://dashboard.render.com/new → Web Service → Connect Repo"
echo ""
echo "Manual trigger: push to main or click 'Manual Deploy' in Render dashboard"
```

## Post-deployment verification
```bash
echo "After deployment, verify:"
echo "  1. Frontend loads: https://attic.to"
echo "  2. Backend health: curl https://api.attic.to/health"
echo "  3. Auth flow: sign in with Google"
echo "  4. Chat: send a test query"
```

## Output

```
## Deployment Checklist

| Check            | Status |
|------------------|--------|
| Tests            | ✓/✗    |
| On main          | ✓/✗    |
| Clean state      | ✓/✗    |
| Up to date       | ✓/✗    |
| No secrets       | ✓/✗    |

{If all pass and not --dry-run}:
Push to main triggers auto-deploy on both Vercel and Render.
Run: git push origin main

{If any fail}:
Fix the issues above before deploying.
```
