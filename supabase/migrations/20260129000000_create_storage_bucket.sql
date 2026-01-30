-- Migration: Create tiktok-exports storage bucket
-- Task: 2-2.1 Supabase Storage Bucket Setup
-- Description: Creates the storage bucket for TikTok export uploads with RLS policies
--              that enforce user-level isolation (users can only access their own files)

-- Create the bucket for TikTok exports
-- Using INSERT with ON CONFLICT to make migration idempotent
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'tiktok-exports',
  'tiktok-exports',
  false,  -- Private bucket (no public access)
  524288000,  -- 500MB in bytes (500 * 1024 * 1024)
  ARRAY['application/zip', 'application/x-zip-compressed', 'application/octet-stream']
)
ON CONFLICT (id) DO UPDATE SET
  public = EXCLUDED.public,
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;

-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS "Users can read own tiktok exports" ON storage.objects;
DROP POLICY IF EXISTS "Users can upload own tiktok exports" ON storage.objects;
DROP POLICY IF EXISTS "Users can update own tiktok exports" ON storage.objects;
DROP POLICY IF EXISTS "Users can delete own tiktok exports" ON storage.objects;

-- RLS Policy: Users can read their own files
-- Path convention: tiktok-exports/{user_id}/{upload_id}.zip
-- Using storage.foldername(name)[1] to extract user_id from path
CREATE POLICY "Users can read own tiktok exports"
ON storage.objects FOR SELECT
USING (
  bucket_id = 'tiktok-exports'
  AND auth.uid()::text = (storage.foldername(name))[1]
);

-- RLS Policy: Users can insert files to their own folder
CREATE POLICY "Users can upload own tiktok exports"
ON storage.objects FOR INSERT
WITH CHECK (
  bucket_id = 'tiktok-exports'
  AND auth.uid()::text = (storage.foldername(name))[1]
);

-- RLS Policy: Users can update their own files
CREATE POLICY "Users can update own tiktok exports"
ON storage.objects FOR UPDATE
USING (
  bucket_id = 'tiktok-exports'
  AND auth.uid()::text = (storage.foldername(name))[1]
);

-- RLS Policy: Users can delete their own files
CREATE POLICY "Users can delete own tiktok exports"
ON storage.objects FOR DELETE
USING (
  bucket_id = 'tiktok-exports'
  AND auth.uid()::text = (storage.foldername(name))[1]
);
