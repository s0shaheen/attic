/**
 * Uppy configuration for TikTok export file uploads.
 *
 * Configures Uppy with restrictions for ZIP files only,
 * 500MB max file size, and single file uploads.
 */

import Uppy from '@uppy/core';

/**
 * Allowed MIME types for TikTok export files.
 * ZIP files may be reported with different MIME types depending on the browser.
 */
export const ALLOWED_FILE_TYPES = [
  'application/zip',
  'application/x-zip-compressed',
  'application/octet-stream',
] as const;

/**
 * Maximum file size in bytes (500MB).
 */
export const MAX_FILE_SIZE = 500 * 1024 * 1024; // 500MB

/**
 * Allowed file extensions for validation.
 */
export const ALLOWED_EXTENSIONS = ['.zip'] as const;

/**
 * Creates a configured Uppy instance for TikTok export uploads.
 *
 * Configuration:
 * - Max file size: 500MB
 * - Max files: 1
 * - Allowed types: ZIP only
 * - Auto-proceed: disabled (user must confirm)
 * - Multiple batches: disabled
 *
 * @returns Configured Uppy instance
 */
export function createUppyInstance(): Uppy<Record<string, unknown>, Record<string, unknown>> {
  return new Uppy({
    id: 'tiktok-uploader',
    restrictions: {
      maxFileSize: MAX_FILE_SIZE,
      maxNumberOfFiles: 1,
      allowedFileTypes: [...ALLOWED_FILE_TYPES],
    },
    autoProceed: false,
    allowMultipleUploadBatches: false,
  });
}

/**
 * Validates that a file is a valid ZIP file.
 *
 * Checks both MIME type and file extension for extra safety.
 *
 * @param file - File to validate
 * @returns true if file is a valid ZIP, false otherwise
 */
export function isValidZipFile(file: File): boolean {
  // Check MIME type
  const hasValidMimeType = ALLOWED_FILE_TYPES.includes(
    file.type as (typeof ALLOWED_FILE_TYPES)[number]
  );

  // Check file extension as backup (some browsers may report wrong MIME type)
  const extension = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
  const hasValidExtension = ALLOWED_EXTENSIONS.includes(
    extension as (typeof ALLOWED_EXTENSIONS)[number]
  );

  return hasValidMimeType || hasValidExtension;
}

/**
 * Formats bytes to a human-readable string.
 *
 * @param bytes - Number of bytes
 * @param decimals - Number of decimal places (default: 2)
 * @returns Formatted string (e.g., "45.5 MB")
 */
export function formatBytes(bytes: number, decimals: number = 2): string {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];

  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const index = Math.min(i, sizes.length - 1);

  return `${parseFloat((bytes / Math.pow(k, index)).toFixed(dm))} ${sizes[index]}`;
}
