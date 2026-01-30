/**
 * Upload API schemas and types.
 *
 * This module defines Zod schemas for the upload API endpoints,
 * providing runtime validation for API requests and responses.
 */

import { z } from 'zod';

/**
 * Request schema for generating a presigned upload URL.
 */
export const presignedUrlRequestSchema = z.object({
  /** Original filename for reference */
  filename: z.string().min(1).max(255),
  /** MIME type of the file (must be ZIP) */
  content_type: z.string().default('application/zip'),
});

/**
 * Response schema for presigned URL generation.
 */
export const presignedUrlResponseSchema = z.object({
  /** Unique identifier for this upload */
  upload_id: z.string().uuid(),
  /** URL to upload file to (valid for 1 hour) */
  presigned_url: z.string().url(),
  /** Path where file will be stored in bucket */
  storage_path: z.string(),
  /** When the presigned URL expires */
  expires_at: z.string().datetime(),
  /** Maximum allowed file size in bytes (500MB) */
  max_file_size: z.number().int().positive(),
});

/**
 * Error response schema for upload operations.
 */
export const uploadErrorResponseSchema = z.object({
  /** Human-readable error message */
  detail: z.string(),
  /** Machine-readable error code */
  code: z.string(),
});

/**
 * Error codes for upload operations.
 */
export const UploadErrorCode = {
  INVALID_CONTENT_TYPE: 'INVALID_CONTENT_TYPE',
  UPLOAD_LIMIT_EXCEEDED: 'UPLOAD_LIMIT_EXCEEDED',
  STORAGE_ERROR: 'STORAGE_ERROR',
} as const;

/**
 * Type definitions inferred from Zod schemas.
 */
export type PresignedUrlRequest = z.infer<typeof presignedUrlRequestSchema>;
export type PresignedUrlResponse = z.infer<typeof presignedUrlResponseSchema>;
export type UploadErrorResponse = z.infer<typeof uploadErrorResponseSchema>;
export type UploadErrorCodeType =
  (typeof UploadErrorCode)[keyof typeof UploadErrorCode];
