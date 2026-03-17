# Attic development commands
# Usage: make dev | make seed | make test-flow | make reset

.PHONY: dev seed test-flow reset backend frontend setup migrate

# One-command setup + start
dev: setup
	@echo ""
	@echo "Starting backend and frontend..."
	@echo "  Backend:  http://localhost:8000"
	@echo "  Frontend: http://localhost:3000"
	@echo ""
	@trap 'kill 0' EXIT; \
		(cd src/backend && uv run uvicorn app.main:app --reload --port 8000) & \
		(cd src/frontend && npm run dev) & \
		wait

# Just the backend
backend:
	cd src/backend && uv run uvicorn app.main:app --reload --port 8000

# Just the frontend
frontend:
	cd src/frontend && npm run dev

# Full setup (idempotent)
setup:
	./scripts/dev-setup.sh

# Run DB migrations
migrate:
	cd src/backend && uv run alembic upgrade head

# Seed test data (works without API keys)
seed:
	cd src/backend && uv run python ../../scripts/seed_local.py

# Run e2e test flow (requires backend running)
test-flow:
	./scripts/test-flow.sh

# Run backend tests
test:
	cd src/backend && uv run pytest tests/ -v

# Wipe local DB and re-setup
reset:
	@echo "Resetting local database..."
	cd src/backend && uv run alembic downgrade base && uv run alembic upgrade head
	@echo "Re-seeding..."
	$(MAKE) seed
	@echo "Reset complete!"
