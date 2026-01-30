# Supabase Storage Setup

This guide covers the TikTok exports storage bucket configuration for Attic.

## Bucket Configuration

The `tiktok-exports` bucket stores user-uploaded TikTok data export ZIP files.

### Settings

| Setting | Value | Description |
|---------|-------|-------------|
| **Bucket Name** | `tiktok-exports` | Unique identifier for the bucket |
| **Public** | `false` | Private bucket, requires authentication |
| **File Size Limit** | 500MB (524,288,000 bytes) | Maximum size per file |
| **Allowed MIME Types** | `application/zip`, `application/x-zip-compressed`, `application/octet-stream` | ZIP files only |

### File Path Convention

All files must follow this path structure:

```
tiktok-exports/{user_id}/{upload_id}.zip
```

- `user_id`: The authenticated user's UUID from Supabase Auth
- `upload_id`: A UUID generated when the upload is initiated

Example: `tiktok-exports/550e8400-e29b-41d4-a716-446655440000/7c9e6679-7425-40de-944b-e07fc1f90ae7.zip`

## RLS Policies

Row Level Security (RLS) policies enforce user isolation. Users can only access files within their own folder.

### Policy Summary

| Policy Name | Operation | Rule |
|-------------|-----------|------|
| Users can read own tiktok exports | SELECT | User can read files where path starts with their user_id |
| Users can upload own tiktok exports | INSERT | User can insert files where path starts with their user_id |
| Users can update own tiktok exports | UPDATE | User can update files where path starts with their user_id |
| Users can delete own tiktok exports | DELETE | User can delete files where path starts with their user_id |

### How RLS Works

The policies use `storage.foldername(name)[1]` to extract the first folder from the file path (the user_id) and compare it to `auth.uid()`:

```sql
CREATE POLICY "Users can read own tiktok exports"
ON storage.objects FOR SELECT
USING (
  bucket_id = 'tiktok-exports'
  AND auth.uid()::text = (storage.foldername(name))[1]
);
```

## Local Development

### Setup

1. Ensure Supabase CLI is installed:
   ```bash
   brew install supabase/tap/supabase
   ```

2. Start local Supabase:
   ```bash
   supabase start
   ```

3. Apply migrations (includes storage bucket creation):
   ```bash
   supabase db reset
   ```

### Verify Bucket

1. Open Supabase Studio: http://127.0.0.1:54323
2. Navigate to Storage in the sidebar
3. Verify `tiktok-exports` bucket exists
4. Check bucket settings match the configuration above

### Manual Bucket Verification

Via SQL in Supabase Studio SQL Editor:

```sql
-- Check bucket exists
SELECT * FROM storage.buckets WHERE id = 'tiktok-exports';

-- Check RLS policies
SELECT policyname, cmd, qual, with_check
FROM pg_policies
WHERE tablename = 'objects' AND schemaname = 'storage';
```

## Production Deployment

### Apply Migration

The bucket is created automatically when running Supabase migrations:

```bash
# Link to your Supabase project (if not already linked)
supabase link --project-ref YOUR_PROJECT_REF

# Push migrations to production
supabase db push
```

### Verify in Dashboard

1. Log in to Supabase Dashboard: https://app.supabase.com
2. Navigate to your project
3. Go to Storage in the sidebar
4. Verify `tiktok-exports` bucket exists with correct settings

## Troubleshooting

### Bucket Not Found

If the bucket doesn't exist after migration:

1. Check migration was applied:
   ```bash
   supabase migration list
   ```

2. If missing, apply migrations:
   ```bash
   supabase db reset  # Local
   supabase db push   # Production
   ```

### Permission Denied on Upload

If users receive "Permission denied" errors:

1. Verify user is authenticated
2. Check file path follows convention: `{user_id}/{upload_id}.zip`
3. Ensure RLS policies exist:
   ```sql
   SELECT * FROM pg_policies WHERE tablename = 'objects' AND schemaname = 'storage';
   ```

### File Size Limit Exceeded

If uploads fail with size errors:

1. Verify the bucket's `file_size_limit` is 524288000 (500MB)
2. TikTok exports larger than 500MB should be split by the user

### MIME Type Rejected

If uploads fail with MIME type errors:

1. Ensure file is a valid ZIP file
2. Check file extension is `.zip`
3. The following MIME types are allowed:
   - `application/zip`
   - `application/x-zip-compressed`
   - `application/octet-stream`

## Security Considerations

- **No Public Access**: The bucket is private; all access requires authentication
- **User Isolation**: RLS policies ensure users can only access their own files
- **Presigned URLs**: Direct file access requires presigned URLs (see Task 2.2)
- **Data Retention**: Raw ZIP files are deleted after parsing (handled in PARSE_EXPORT Lambda)

## Related Documentation

- [Supabase Setup](./supabase.md) - General Supabase configuration
- [Local Development](./local-dev.md) - Local development environment setup
