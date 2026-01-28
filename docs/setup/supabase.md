# Supabase Setup

This guide covers setting up Supabase for Attic development.

## Cloud Project

The Attic cloud Supabase project is already configured:

- **Project URL**: `https://tuxjegaeacqsxfmtokwy.supabase.co`
- **Region**: AWS us-east-1

### Required Environment Variables

Add these to your `.env.local`:

```bash
# Supabase (required)
SUPABASE_URL=https://tuxjegaeacqsxfmtokwy.supabase.co
SUPABASE_ANON_KEY=<from Supabase Dashboard>
SUPABASE_SERVICE_ROLE_KEY=<from Supabase Dashboard>

# Database password (for direct connection)
# Find in: Supabase Dashboard > Project Settings > Database > Connection string
SUPABASE_DB_PASSWORD=<database password>
```

## Local Development

For local development, use the Supabase CLI to run a local instance.

### Prerequisites

```bash
# Install Supabase CLI (macOS)
brew install supabase/tap/supabase

# Verify installation
supabase --version
```

### Start Local Supabase

```bash
# From project root
supabase start

# This starts:
# - PostgreSQL (port 54322)
# - Supabase API (port 54321)
# - Supabase Studio (port 54323)
# - Auth, Storage, Realtime services
```

### Local Connection

For local development, set:

```bash
USE_LOCAL_SUPABASE=true
```

Or connect directly:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres
```

### Supabase Studio

Access the local admin UI at: http://127.0.0.1:54323

### Stop Local Supabase

```bash
supabase stop

# To also reset data:
supabase stop --no-backup
```

## Database Connection

### Python (SQLAlchemy)

```python
from app.db import get_db, async_session_factory

# FastAPI dependency injection
@router.get("/items")
async def list_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item))
    return result.scalars().all()

# Direct session usage
async with async_session_factory()() as session:
    result = await session.execute(select(Item))
```

### Connection Priority

The `build_database_url()` function checks in order:
1. `DATABASE_URL` - direct connection string
2. `USE_LOCAL_SUPABASE=true` - local Supabase CLI
3. `SUPABASE_URL` + `SUPABASE_DB_PASSWORD` - cloud Supabase

## Extensions

The following PostgreSQL extensions are enabled:

- **pgvector** - Vector similarity search for embeddings
- **pg_trgm** - Trigram matching for fuzzy text search

These are enabled in the seed file and migrations.

## Storage

A storage bucket named `uploads` will be created for TikTok export files:

- **Bucket**: `uploads`
- **Public**: No (requires authentication)
- **Max file size**: 500MB

## Troubleshooting

### Connection Refused

If you get "connection refused" errors:

1. Check if local Supabase is running: `supabase status`
2. Verify the port in `supabase/config.toml`
3. Check `USE_LOCAL_SUPABASE` is set for local dev

### Permission Denied

For cloud connections:
1. Verify `SUPABASE_DB_PASSWORD` is correct
2. Check the connection string format uses the pooler URL
3. Ensure your IP is not blocked (check Supabase Dashboard > Database)

### pgvector Not Found

Run the seed file or migration to enable the extension:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```
