import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  presignedUrlRequestSchema,
  presignedUrlResponseSchema,
  uploadErrorResponseSchema,
  getPresignedUrl,
  UploadApiError,
  UploadErrorCode,
} from '@/lib/api/uploads';

describe('Upload API', () => {
  describe('presignedUrlRequestSchema', () => {
    it('validates valid request', () => {
      const result = presignedUrlRequestSchema.safeParse({
        filename: 'tiktok-export.zip',
        content_type: 'application/zip',
      });
      expect(result.success).toBe(true);
    });

    it('uses default content_type if not provided', () => {
      const result = presignedUrlRequestSchema.parse({
        filename: 'tiktok-export.zip',
      });
      expect(result.content_type).toBe('application/zip');
    });

    it('rejects empty filename', () => {
      const result = presignedUrlRequestSchema.safeParse({
        filename: '',
        content_type: 'application/zip',
      });
      expect(result.success).toBe(false);
    });

    it('rejects filename over 255 characters', () => {
      const result = presignedUrlRequestSchema.safeParse({
        filename: 'a'.repeat(256),
        content_type: 'application/zip',
      });
      expect(result.success).toBe(false);
    });
  });

  describe('presignedUrlResponseSchema', () => {
    it('validates valid response', () => {
      const result = presignedUrlResponseSchema.safeParse({
        upload_id: '123e4567-e89b-12d3-a456-426614174000',
        presigned_url: 'https://storage.example.com/upload',
        storage_path: 'user-id/upload-id.zip',
        expires_at: '2026-01-29T12:00:00Z',
        max_file_size: 524288000,
      });
      expect(result.success).toBe(true);
    });

    it('rejects invalid UUID', () => {
      const result = presignedUrlResponseSchema.safeParse({
        upload_id: 'not-a-uuid',
        presigned_url: 'https://storage.example.com/upload',
        storage_path: 'user-id/upload-id.zip',
        expires_at: '2026-01-29T12:00:00Z',
        max_file_size: 524288000,
      });
      expect(result.success).toBe(false);
    });

    it('rejects invalid URL', () => {
      const result = presignedUrlResponseSchema.safeParse({
        upload_id: '123e4567-e89b-12d3-a456-426614174000',
        presigned_url: 'not-a-url',
        storage_path: 'user-id/upload-id.zip',
        expires_at: '2026-01-29T12:00:00Z',
        max_file_size: 524288000,
      });
      expect(result.success).toBe(false);
    });
  });

  describe('uploadErrorResponseSchema', () => {
    it('validates valid error response', () => {
      const result = uploadErrorResponseSchema.safeParse({
        detail: 'Upload limit exceeded',
        code: 'UPLOAD_LIMIT_EXCEEDED',
      });
      expect(result.success).toBe(true);
    });
  });

  describe('UploadErrorCode', () => {
    it('has expected error codes', () => {
      expect(UploadErrorCode.INVALID_CONTENT_TYPE).toBe('INVALID_CONTENT_TYPE');
      expect(UploadErrorCode.UPLOAD_LIMIT_EXCEEDED).toBe('UPLOAD_LIMIT_EXCEEDED');
      expect(UploadErrorCode.STORAGE_ERROR).toBe('STORAGE_ERROR');
    });
  });

  describe('UploadApiError', () => {
    it('creates error with correct properties', () => {
      const error = new UploadApiError(
        'Upload failed',
        'STORAGE_ERROR',
        500
      );
      expect(error.message).toBe('Upload failed');
      expect(error.code).toBe('STORAGE_ERROR');
      expect(error.status).toBe(500);
      expect(error.name).toBe('UploadApiError');
    });
  });

  describe('getPresignedUrl', () => {
    const originalFetch = global.fetch;

    beforeEach(() => {
      vi.stubGlobal('process', {
        ...process,
        env: {
          ...process.env,
          NEXT_PUBLIC_API_URL: 'http://localhost:8000',
        },
      });
    });

    afterEach(() => {
      global.fetch = originalFetch;
      vi.unstubAllGlobals();
    });

    it('returns presigned URL response on success', async () => {
      const mockResponse = {
        upload_id: '123e4567-e89b-12d3-a456-426614174000',
        presigned_url: 'https://storage.example.com/upload',
        storage_path: 'user-id/upload-id.zip',
        expires_at: '2026-01-29T12:00:00Z',
        max_file_size: 524288000,
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await getPresignedUrl(
        { filename: 'export.zip', content_type: 'application/zip' },
        'mock-token'
      );

      expect(result).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/uploads/presigned-url',
        expect.objectContaining({
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: 'Bearer mock-token',
          },
        })
      );
    });

    it('throws UploadApiError on error response', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: () =>
          Promise.resolve({
            detail: 'Upload limit exceeded',
            code: 'UPLOAD_LIMIT_EXCEEDED',
          }),
      });

      await expect(
        getPresignedUrl(
          { filename: 'export.zip', content_type: 'application/zip' },
          'mock-token'
        )
      ).rejects.toThrow(UploadApiError);
    });

    it('throws error when API URL is not configured', async () => {
      vi.stubGlobal('process', {
        ...process,
        env: {},
      });

      await expect(
        getPresignedUrl(
          { filename: 'export.zip', content_type: 'application/zip' },
          'mock-token'
        )
      ).rejects.toThrow('API URL not configured');
    });
  });
});
