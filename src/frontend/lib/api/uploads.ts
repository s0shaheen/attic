/**
 * Upload API schemas and types.
 *
 * This module defines Zod schemas for the upload API endpoints,
 * providing runtime validation for API requests and responses,
 * including presigned URL generation and scope selection.
 */

import { z } from 'zod';

// ============================================================================
// Presigned URL (Task 2-2.2)
// ============================================================================

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

/**
 * Error thrown when upload API request fails.
 */
export class UploadApiError extends Error {
  constructor(
    message: string,
    public readonly code: UploadErrorCodeType | 'UNKNOWN_ERROR',
    public readonly status: number
  ) {
    super(message);
    this.name = 'UploadApiError';
  }
}

/**
 * Fetches a presigned URL for uploading a TikTok export file.
 *
 * Makes an authenticated request to the backend API to get a presigned URL
 * that can be used to upload a file directly to Supabase Storage.
 *
 * @param request - Request containing filename and content_type
 * @param accessToken - Supabase JWT access token for authentication
 * @returns Presigned URL response containing upload_id, presigned_url, storage_path, expires_at
 * @throws UploadApiError if the request fails
 */
export async function getPresignedUrl(
  request: PresignedUrlRequest,
  accessToken: string
): Promise<PresignedUrlResponse> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!apiUrl) {
    throw new UploadApiError(
      'API URL not configured',
      'UNKNOWN_ERROR',
      500
    );
  }

  const response = await fetch(`${apiUrl}/api/uploads/presigned-url`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    // Try to parse error response
    let errorMessage = 'Failed to get presigned URL';
    let errorCode: UploadErrorCodeType | 'UNKNOWN_ERROR' = 'UNKNOWN_ERROR';

    try {
      const errorData = await response.json();
      const parsed = uploadErrorResponseSchema.safeParse(errorData);
      if (parsed.success) {
        errorMessage = parsed.data.detail;
        errorCode = parsed.data.code as UploadErrorCodeType;
      }
    } catch {
      // Ignore JSON parse errors, use default message
    }

    throw new UploadApiError(errorMessage, errorCode, response.status);
  }

  const data = await response.json();
  const parsed = presignedUrlResponseSchema.safeParse(data);

  if (!parsed.success) {
    throw new UploadApiError(
      'Invalid response from server',
      'UNKNOWN_ERROR',
      500
    );
  }

  return parsed.data;
}

// ============================================================================
// Scope Selection (Task 2-2.6)
// ============================================================================

/**
 * Valid scope options for video processing.
 */
export const scopeSchema = z.enum(["liked", "favorited", "both"]);
export type Scope = z.infer<typeof scopeSchema>;

/**
 * Request to set the processing scope.
 */
export const scopeSelectionRequestSchema = z.object({
  scope: scopeSchema,
});
export type ScopeSelectionRequest = z.infer<typeof scopeSelectionRequestSchema>;

/**
 * Response after successful scope selection.
 */
export const scopeSelectionResponseSchema = z.object({
  upload_id: z.string().uuid(),
  scope: scopeSchema,
  total_items: z.number().int().nonnegative(),
  liked_count: z.number().int().nonnegative(),
  favorited_count: z.number().int().nonnegative(),
  tier_limit: z.number().int().positive(),
  within_limit: z.boolean(),
  estimated_processing_minutes: z.number().int().nonnegative(),
  ready_for_consent: z.boolean(),
});
export type ScopeSelectionResponse = z.infer<typeof scopeSelectionResponseSchema>;

/**
 * Error response when scope exceeds tier limit.
 */
export const tierLimitExceededErrorSchema = z.object({
  error: z.literal("TIER_LIMIT_EXCEEDED"),
  message: z.string(),
  selected_count: z.number().int().nonnegative(),
  tier_limit: z.number().int().positive(),
  tier: z.string(),
  upgrade_required: z.boolean(),
});
export type TierLimitExceededError = z.infer<typeof tierLimitExceededErrorSchema>;

// ============================================================================
// Tier Information
// ============================================================================

/**
 * Subscription tier names.
 */
export const tierSchema = z.enum(["free", "explorer", "expert", "pioneer"]);
export type Tier = z.infer<typeof tierSchema>;

/**
 * Tier video limits (from PRD).
 */
export const TIER_LIMITS: Record<Tier, number> = {
  free: 200,
  explorer: 1_500,
  expert: 3_000,
  pioneer: 7_500,
};

/**
 * Get the video limit for a tier.
 */
export function getTierLimit(tier: Tier): number {
  return TIER_LIMITS[tier];
}

/**
 * Check if a count is within a tier's limit.
 */
export function isWithinTierLimit(tier: Tier, count: number): boolean {
  return count <= TIER_LIMITS[tier];
}

/**
 * Get the lowest tier that can accommodate a video count.
 */
export function getTierThatFits(count: number): Tier | null {
  const tiers: Tier[] = ["free", "explorer", "expert", "pioneer"];
  for (const tier of tiers) {
    if (TIER_LIMITS[tier] >= count) {
      return tier;
    }
  }
  return null;
}
