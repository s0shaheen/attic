---
description: Start the local development stack. Handles backend and frontend with health checks.
argument-hint: "[--backend-only] [--no-seed]"
---

## Steps

### 1. Check prerequisites
```bash
# Env files exist
[ -f "src/backend/.env" ] || echo "ERROR: Backend env missing. Run ./scripts/setup-env.sh"
[ -f "src/frontend/.env.local" ] || echo "ERROR: Frontend env missing. Run ./scripts/setup-env.sh"
```

If any prerequisite fails, print the specific fix and stop.

### 2. Check Supabase connectivity
```bash
SUPABASE_URL=$(grep '^SUPABASE_URL=' src/backend/.env | cut -d= -f2- | tr -d '"')
# Any HTTP response means reachable (even 401 from dummy apikey)
if curl -s --max-time 5 -o /dev/null -w "%{http_code}" "${SUPABASE_URL}/auth/v1/settings" -H "apikey: dummy" 2>/dev/null | grep -q "^[2-5]"; then
    echo "Supabase reachable at ${SUPABASE_URL}"
else
    echo "WARNING: Cannot reach Supabase at ${SUPABASE_URL}"
fi
```

### 3. Run migrations
```bash
cd src/backend
../../.venv/bin/alembic upgrade head 2>&1 | tail -3
cd ../..
```

### 4. Seed database (unless --no-seed)
```bash
if [ -f "workbench/scripts/seed_db.py" ]; then
    .venv/bin/python workbench/scripts/seed_db.py 2>&1 | tail -5
else
    echo "No seed script found — skipping"
fi
```

### 5. Start backend
```bash
cd src/backend
../../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ../..
```

Wait for health check:
```bash
for i in {1..15}; do
    curl -s http://localhost:8000/health > /dev/null && break
    sleep 1
done
```

### 6. Start frontend (unless --backend-only)
```bash
cd src/frontend
npm run dev &
FRONTEND_PID=$!
cd ../..
```

### 7. Report
```
## Local Stack Running

| Service        | URL                        | Status |
|----------------|----------------------------|--------|
| Backend API    | http://localhost:8000       | ✓      |
| API Docs       | http://localhost:8000/docs  | ✓      |
| Frontend       | http://localhost:3000       | ✓      |
| Supabase       | Cloud (always on)          | ✓      |

Dashboard: https://supabase.com/dashboard
Test account: test@attic.to / testpassword123

To stop: Ctrl+C or ./scripts/dev-stop.sh
```
