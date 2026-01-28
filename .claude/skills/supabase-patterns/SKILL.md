---
name: supabase-patterns
description: Patterns for Supabase Auth, Storage, Realtime, and RLS in Attic. Use when implementing authentication, file uploads, real-time subscriptions, or database security policies.
---

# Supabase Patterns for Attic

## Authentication

### Validating JWT in FastAPI

```python
# src/backend/app/core/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from app.core.config import settings

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Validate Supabase JWT and return user data.
    
    CRITICAL: Always derive user_id from the token, never trust client.
    """
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )
        return {
            "user_id": payload["sub"],
            "email": payload.get("email"),
            "role": payload.get("role", "authenticated")
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
```

### Using Auth in Endpoints

```python
from fastapi import APIRouter, Depends
from app.core.auth import get_current_user

router = APIRouter()

@router.get("/uploads")
async def list_uploads(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # user["user_id"] is guaranteed from valid JWT
    return await upload_repo.list_by_user(db, user["user_id"])
```

### Frontend Auth Setup

```typescript
// src/frontend/lib/supabase/client.ts
import { createBrowserClient } from '@supabase/ssr';

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
```

```typescript
// src/frontend/lib/supabase/server.ts
import { createServerClient, type CookieOptions } from '@supabase/ssr';
import { cookies } from 'next/headers';

export function createClient() {
  const cookieStore = cookies();
  
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        get(name: string) {
          return cookieStore.get(name)?.value;
        },
        set(name: string, value: string, options: CookieOptions) {
          cookieStore.set({ name, value, ...options });
        },
        remove(name: string, options: CookieOptions) {
          cookieStore.set({ name, value: '', ...options });
        },
      },
    }
  );
}
```

## Storage

### Presigned Upload URLs

```python
# src/backend/app/services/storage.py
from uuid import uuid4
from supabase import create_client
from app.core.config import settings

async def create_upload_url(user_id: str, filename: str) -> dict:
    """
    Generate presigned URL for direct upload to Supabase Storage.
    
    Path includes user_id for RLS enforcement.
    """
    supabase = create_client(
        settings.SUPABASE_URL, 
        settings.SUPABASE_SERVICE_ROLE_KEY
    )
    
    # Path structure: {user_id}/{upload_id}/{filename}
    upload_id = str(uuid4())
    path = f"{user_id}/{upload_id}/{filename}"
    
    # URL valid for 1 hour
    result = supabase.storage.from_("uploads").create_signed_upload_url(path)
    
    return {
        "signed_url": result["signedUrl"],
        "path": path,
        "upload_id": upload_id
    }
```

### Storage RLS Policies

```sql
-- Users can only upload to their own folder
CREATE POLICY "Users upload to own folder"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (
    bucket_id = 'uploads' AND
    (storage.foldername(name))[1] = auth.uid()::text
);

-- Users can only read their own uploads
CREATE POLICY "Users read own uploads"
ON storage.objects FOR SELECT
TO authenticated
USING (
    bucket_id = 'uploads' AND
    (storage.foldername(name))[1] = auth.uid()::text
);

-- Users can delete their own uploads
CREATE POLICY "Users delete own uploads"
ON storage.objects FOR DELETE
TO authenticated
USING (
    bucket_id = 'uploads' AND
    (storage.foldername(name))[1] = auth.uid()::text
);
```

## Realtime

### Subscribe to Pipeline Progress

```typescript
// src/frontend/hooks/usePipelineProgress.ts
import { useEffect, useState } from 'react';
import { createClient } from '@/lib/supabase/client';
import type { RealtimeChannel } from '@supabase/supabase-js';

interface PipelineProgress {
  upload_id: string;
  status: 'pending' | 'processing' | 'complete' | 'failed';
  videos_enriched: number;
  videos_complete: number;
  total_videos: number;
  estimated_completion_at: string | null;
}

export function usePipelineProgress(uploadId: string) {
  const [progress, setProgress] = useState<PipelineProgress | null>(null);
  const [error, setError] = useState<Error | null>(null);
  
  useEffect(() => {
    const supabase = createClient();
    let channel: RealtimeChannel;
    
    async function subscribe() {
      // First fetch current state
      const { data, error: fetchError } = await supabase
        .from('upload_pipeline_runs')
        .select('*')
        .eq('upload_id', uploadId)
        .single();
      
      if (fetchError) {
        setError(fetchError);
        return;
      }
      
      setProgress(data);
      
      // Then subscribe to updates
      channel = supabase
        .channel(`pipeline:${uploadId}`)
        .on(
          'postgres_changes',
          {
            event: 'UPDATE',
            schema: 'public',
            table: 'upload_pipeline_runs',
            filter: `upload_id=eq.${uploadId}`
          },
          (payload) => {
            setProgress(payload.new as PipelineProgress);
          }
        )
        .subscribe();
    }
    
    subscribe();
    
    return () => {
      if (channel) {
        supabase.removeChannel(channel);
      }
    };
  }, [uploadId]);
  
  return { progress, error };
}
```

### Enable Realtime for Table

```sql
-- Run in Supabase SQL Editor
ALTER PUBLICATION supabase_realtime ADD TABLE upload_pipeline_runs;
```

## Row Level Security (RLS)

### Standard User-Owned Table Pattern

```sql
-- Enable RLS (do this first!)
ALTER TABLE uploads ENABLE ROW LEVEL SECURITY;

-- SELECT: Users see only their own data
CREATE POLICY "Users view own uploads"
ON uploads FOR SELECT
TO authenticated
USING (user_id = auth.uid());

-- INSERT: Users can only create records for themselves
CREATE POLICY "Users create own uploads"
ON uploads FOR INSERT
TO authenticated
WITH CHECK (user_id = auth.uid());

-- UPDATE: Users can only update their own records
CREATE POLICY "Users update own uploads"
ON uploads FOR UPDATE
TO authenticated
USING (user_id = auth.uid())
WITH CHECK (user_id = auth.uid());

-- DELETE: Users can only delete their own records
CREATE POLICY "Users delete own uploads"
ON uploads FOR DELETE
TO authenticated
USING (user_id = auth.uid());
```

### Testing RLS Policies

```python
# tests/integration/test_rls.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_user_cannot_see_other_users_uploads(
    client: AsyncClient,
    user_a_token: str,
    user_b_upload: Upload
):
    """Verify RLS blocks cross-user data access."""
    response = await client.get(
        f"/api/uploads/{user_b_upload.id}",
        headers={"Authorization": f"Bearer {user_a_token}"}
    )
    
    # Return 404 not 403 - don't reveal existence
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_can_see_own_uploads(
    client: AsyncClient,
    user_a_token: str,
    user_a_upload: Upload
):
    """Verify user can access their own data."""
    response = await client.get(
        f"/api/uploads/{user_a_upload.id}",
        headers={"Authorization": f"Bearer {user_a_token}"}
    )
    
    assert response.status_code == 200
    assert response.json()["id"] == str(user_a_upload.id)
```

## Service Role Access (Backend Only)

For backend operations that need to bypass RLS:

```python
# Use service role key for admin operations
from supabase import create_client

def get_admin_client():
    """
    Get Supabase client with service role.
    ONLY use in backend for admin operations.
    """
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY
    )
```

**CRITICAL**: Never expose service role key to frontend.
