# Attic Local Development Setup

This guide explains how to set up and run the Attic development environment locally.

## Prerequisites

Before starting, ensure you have the following installed:

### Required

1. **Docker Desktop** (v4.0+)
   - macOS: `brew install --cask docker`
   - Or download from: https://www.docker.com/products/docker-desktop

2. **Supabase CLI** (v1.0+)
   - macOS: `brew install supabase/tap/supabase`
   - Other: https://supabase.com/docs/guides/cli

3. **Node.js** (v20+)
   - macOS: `brew install node@20`
   - Or use nvm: `nvm install 20`

4. **Python** (v3.13+)
   - macOS: `brew install python@3.13`

### Optional (for AWS local testing)

5. **AWS CLI Local** (awslocal wrapper)
   - `pip install awscli-local`
   - Provides `awslocal` command for LocalStack

## Quick Start

```bash
# 1. Clone the repository (if you haven't)
git clone https://github.com/your-org/attic.git
cd attic

# 2. Make scripts executable
chmod +x scripts/*.sh .docker/localstack/*.sh

# 3. Start all services
./scripts/dev-start.sh

# 4. Start frontend (in a separate terminal)
cd src/frontend
npm install
npm run dev
```

## Service URLs

Once running, the following services are available:

| Service           | URL                                                    |
|-------------------|--------------------------------------------------------|
| Frontend          | http://localhost:3000                                  |
| Backend API       | http://localhost:8000                                  |
| API Documentation | http://localhost:8000/docs                             |
| Supabase Studio   | http://localhost:54323                                 |
| Supabase API      | http://localhost:54321                                 |
| Supabase DB       | postgresql://postgres:postgres@localhost:54322/postgres|
| LocalStack        | http://localhost:4566                                  |

## Architecture

```
                    +------------------+
                    |   Frontend       |
                    |   (Next.js)      |
                    |   :3000          |
                    +--------+---------+
                             |
                             v
+------------------+   +------------------+   +------------------+
|   Supabase       |<--|   Backend API    |-->|   LocalStack     |
|   (Auth, DB,     |   |   (FastAPI)      |   |   (S3, SQS,      |
|   Storage)       |   |   :8000          |   |   Step Functions)|
|   :54321-54323   |   +------------------+   |   :4566          |
+------------------+                          +------------------+
```

## Common Commands

### Starting and Stopping

```bash
# Start all services
./scripts/dev-start.sh

# Start without rebuilding (faster)
./scripts/dev-start.sh --skip-supabase

# Force rebuild containers
./scripts/dev-start.sh --build

# Stop all services
./scripts/dev-stop.sh

# Stop but keep Supabase running
./scripts/dev-stop.sh --keep-supabase
```

### Viewing Logs

```bash
# All Docker services
docker compose logs -f

# Backend only
docker compose logs -f backend

# LocalStack only
docker compose logs -f localstack

# Supabase logs
supabase logs
```

### Database Operations

```bash
# Open Supabase Studio (GUI)
open http://localhost:54323

# Run migrations
cd src/backend
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"

# Reset database
supabase db reset

# Connect with psql
psql postgresql://postgres:postgres@localhost:54322/postgres
```

### LocalStack (AWS Emulation)

```bash
# List S3 buckets
awslocal s3 ls

# List objects in bucket
awslocal s3 ls s3://attic-temp-media

# Upload a test file
awslocal s3 cp test.txt s3://attic-temp-media/

# List SQS queues
awslocal sqs list-queues

# Send a test message to queue
awslocal sqs send-message \
  --queue-url http://localhost:4566/000000000000/attic-upload-queue \
  --message-body '{"test": true}'

# List Step Functions state machines
awslocal stepfunctions list-state-machines
```

### Testing

```bash
# Backend tests
cd src/backend
pytest tests/ -v

# Frontend tests
cd src/frontend
npm test

# Run specific test file
pytest tests/test_health.py -v
```

### Linting and Formatting

```bash
# Backend
cd src/backend
ruff check .     # Lint
ruff format .    # Format

# Frontend
cd src/frontend
npm run lint     # Lint
npm run typecheck  # Type check
```

## Resetting the Environment

If you need to start fresh:

```bash
# Reset all data (keeps volumes)
./scripts/dev-reset.sh

# Hard reset (removes volumes too)
./scripts/dev-reset.sh --hard
```

## Troubleshooting

### Docker Compose fails to start

1. Ensure Docker Desktop is running:
   ```bash
   docker info
   ```

2. Check if ports are in use:
   ```bash
   lsof -i :8000  # Backend
   lsof -i :4566  # LocalStack
   ```

3. Try rebuilding:
   ```bash
   docker compose down -v
   docker compose up -d --build
   ```

### Supabase won't start

1. Check if ports are in use:
   ```bash
   lsof -i :54321
   lsof -i :54322
   lsof -i :54323
   ```

2. Reset Supabase:
   ```bash
   supabase stop
   supabase start
   ```

### Backend can't connect to database

1. Verify Supabase is running:
   ```bash
   supabase status
   ```

2. Check the database URL:
   ```bash
   # Should be: postgresql://postgres:postgres@localhost:54322/postgres
   psql postgresql://postgres:postgres@localhost:54322/postgres -c "SELECT 1"
   ```

3. For Docker backend, ensure `host.docker.internal` resolves:
   ```bash
   docker compose exec backend ping host.docker.internal
   ```

### LocalStack services not initialized

1. Check LocalStack logs:
   ```bash
   docker compose logs localstack
   ```

2. Manually run initialization:
   ```bash
   docker compose exec localstack bash /etc/localstack/init/ready.d/init-aws.sh
   ```

3. Verify services:
   ```bash
   curl http://localhost:4566/_localstack/health
   ```

### Frontend can't reach backend

1. Ensure backend is healthy:
   ```bash
   curl http://localhost:8000/health
   ```

2. Check CORS configuration in backend

3. Verify environment variables in `src/frontend/.env.local`

## Environment Variables

### Backend (.env.local in src/backend/)

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres

# Supabase
SUPABASE_URL=http://localhost:54321
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key

# AWS (LocalStack)
AWS_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_DEFAULT_REGION=us-east-1

# Application
ENVIRONMENT=local
DEBUG=true
```

### Frontend (.env.local in src/frontend/)

```bash
NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Development Workflow

1. **Start services**: `./scripts/dev-start.sh`
2. **Start frontend**: `cd src/frontend && npm run dev`
3. **Make changes**: Code changes hot-reload automatically
4. **Run tests**: `pytest` (backend) or `npm test` (frontend)
5. **Check linting**: `ruff check .` (backend) or `npm run lint` (frontend)
6. **Stop services**: `./scripts/dev-stop.sh`

## Additional Resources

- [Supabase Local Development](https://supabase.com/docs/guides/local-development)
- [LocalStack Documentation](https://docs.localstack.cloud/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
