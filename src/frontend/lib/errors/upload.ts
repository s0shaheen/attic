/**
 * Upload validation error types and messages.
 *
 * This module defines Zod schemas for validation errors returned by the
 * upload validation API, and user-friendly error messages for each error code.
 */

import { z } from "zod";

/**
 * Error codes for validation failures.
 */
export const validationErrorCodeSchema = z.enum([
  "INVALID_FILE",
  "INVALID_EXPORT",
  "EMPTY_EXPORT",
  "FILE_TOO_LARGE",
  "FILE_CORRUPTED",
  "UNSUPPORTED_FORMAT",
]);

export type ValidationErrorCode = z.infer<typeof validationErrorCodeSchema>;

/**
 * Validation result from the API.
 */
export const validationResultSchema = z.object({
  valid: z.boolean(),
  error_code: validationErrorCodeSchema.nullable(),
  error_message: z.string().nullable(),
  liked_count: z.number().nullable(),
  favorited_count: z.number().nullable(),
  file_hash: z.string().nullable(),
});

export type ValidationResult = z.infer<typeof validationResultSchema>;

/**
 * Full response from the validation endpoint.
 */
export const validateUploadResponseSchema = z.object({
  upload_id: z.string().uuid(),
  validation: validationResultSchema,
});

export type ValidateUploadResponse = z.infer<typeof validateUploadResponseSchema>;

/**
 * User-friendly error messages for each validation error code.
 *
 * Each error has:
 * - title: Short, scannable heading
 * - description: Helpful explanation with actionable guidance
 */
export const ERROR_MESSAGES: Record<
  ValidationErrorCode,
  { title: string; description: string }
> = {
  INVALID_FILE: {
    title: "Not a valid ZIP file",
    description:
      "Please upload a ZIP file from your TikTok data export.",
  },
  INVALID_EXPORT: {
    title: "Not a TikTok export",
    description:
      "This ZIP file doesn't contain a TikTok data export. Make sure you're uploading the file from TikTok's \"Download your data\" feature.",
  },
  EMPTY_EXPORT: {
    title: "No videos found",
    description:
      "Your export doesn't contain any liked or favorited videos. Make sure you have liked or favorited videos on TikTok.",
  },
  FILE_TOO_LARGE: {
    title: "File too large",
    description:
      "The maximum file size is 500MB. Please contact support if your export is larger.",
  },
  FILE_CORRUPTED: {
    title: "File is corrupted",
    description:
      "The ZIP file appears to be corrupted. Please re-download your export from TikTok.",
  },
  UNSUPPORTED_FORMAT: {
    title: "Wrong format",
    description:
      "Please make sure you selected \"JSON\" format when requesting your TikTok data export.",
  },
};

/**
 * Get the user-friendly error message for a validation error code.
 *
 * @param errorCode - The validation error code from the API
 * @returns The error message object with title and description
 */
export function getValidationErrorMessage(
  errorCode: ValidationErrorCode
): { title: string; description: string } {
  return ERROR_MESSAGES[errorCode];
}

/**
 * Check if an error code is a validation error code.
 *
 * @param code - The error code to check
 * @returns True if valid validation error code
 */
export function isValidationErrorCode(
  code: string
): code is ValidationErrorCode {
  return validationErrorCodeSchema.safeParse(code).success;
}
