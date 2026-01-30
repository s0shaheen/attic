"use client";

/**
 * TikTok export file uploader component.
 *
 * Provides drag-and-drop file upload functionality using Uppy
 * with direct-to-storage uploads via presigned URLs.
 */

import * as React from "react";
import { z } from "zod";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useUppy, type UploadResult as HookUploadResult } from "@/hooks/useUppy";
import { UploadProgress } from "./UploadProgress";
import { UploadError } from "./UploadError";
import {
  MAX_FILE_SIZE,
  ALLOWED_FILE_TYPES,
  ALLOWED_EXTENSIONS,
  formatBytes,
} from "@/lib/uppy/config";
import { Upload, FileArchive } from "lucide-react";

/**
 * Schema for upload result validation.
 */
export const uploadResultSchema = z.object({
  uploadId: z.string().uuid(),
  storagePath: z.string(),
  filename: z.string(),
});

/**
 * Result returned when upload completes successfully.
 */
export type UploadResult = z.infer<typeof uploadResultSchema>;

/**
 * Props for the TikTokUploader component.
 */
export interface TikTokUploaderProps {
  /** Called when upload completes successfully */
  onUploadComplete: (result: UploadResult) => void;
  /** Called when upload fails */
  onUploadError?: (error: Error) => void;
  /** Called when upload is cancelled */
  onUploadCancel?: () => void;
  /** Maximum file size in bytes (default: 500MB) */
  maxFileSize?: number;
  /** Whether the uploader is disabled */
  disabled?: boolean;
  /** Custom class name for styling */
  className?: string;
}

/**
 * TikTok export file uploader with drag-and-drop support.
 *
 * Features:
 * - Drag-and-drop file selection
 * - Click to browse file picker
 * - Real-time upload progress
 * - Error handling with retry
 * - Upload cancellation
 * - File type and size validation
 *
 * @example
 * ```tsx
 * <TikTokUploader
 *   onUploadComplete={(result) => {
 *     console.log('Uploaded:', result.uploadId);
 *     router.push(`/uploads/${result.uploadId}/configure`);
 *   }}
 *   onUploadError={(error) => {
 *     console.error('Upload failed:', error);
 *   }}
 * />
 * ```
 */
export function TikTokUploader({
  onUploadComplete,
  onUploadError,
  onUploadCancel,
  maxFileSize = MAX_FILE_SIZE,
  disabled = false,
  className,
}: TikTokUploaderProps) {
  const [isDragOver, setIsDragOver] = React.useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const {
    state,
    addFile,
    startUpload,
    cancelUpload,
    reset,
    bytesUploadedFormatted,
    bytesTotalFormatted,
  } = useUppy({
    onUploadComplete: (result: HookUploadResult) => {
      // Validate result with Zod schema
      const parsed = uploadResultSchema.safeParse(result);
      if (parsed.success) {
        onUploadComplete(parsed.data);
      } else {
        const error = new Error("Invalid upload result from server");
        onUploadError?.(error);
      }
    },
    onUploadError,
    onUploadCancel,
  });

  /**
   * Handles file validation before adding to upload queue.
   */
  const handleFile = React.useCallback(
    (file: File) => {
      // Check file extension
      const extension = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
      const hasValidExtension = ALLOWED_EXTENSIONS.includes(
        extension as (typeof ALLOWED_EXTENSIONS)[number]
      );

      // Check MIME type
      const hasValidMimeType = ALLOWED_FILE_TYPES.includes(
        file.type as (typeof ALLOWED_FILE_TYPES)[number]
      );

      // Allow if either extension or MIME type is valid
      // (some browsers report wrong MIME type for ZIP files)
      if (!hasValidExtension && !hasValidMimeType) {
        const error = new Error(
          "Invalid file type. Please select a ZIP file from your TikTok data export."
        );
        onUploadError?.(error);
        return;
      }

      // Check file size
      if (file.size > maxFileSize) {
        const error = new Error(
          `File size exceeds the maximum limit of ${formatBytes(maxFileSize)}.`
        );
        onUploadError?.(error);
        return;
      }

      addFile(file);
    },
    [addFile, maxFileSize, onUploadError]
  );

  /**
   * Handles drag over event.
   */
  const handleDragOver = React.useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      if (!disabled) {
        setIsDragOver(true);
      }
    },
    [disabled]
  );

  /**
   * Handles drag leave event.
   */
  const handleDragLeave = React.useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);
    },
    []
  );

  /**
   * Handles file drop event.
   */
  const handleDrop = React.useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);

      if (disabled) return;

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        handleFile(files[0]);
      }
    },
    [disabled, handleFile]
  );

  /**
   * Handles file input change event.
   */
  const handleFileInputChange = React.useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        handleFile(files[0]);
      }
      // Reset input so the same file can be selected again
      e.target.value = "";
    },
    [handleFile]
  );

  /**
   * Opens the file picker dialog.
   */
  const handleBrowseClick = React.useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  /**
   * Handles retry after error.
   */
  const handleRetry = React.useCallback(() => {
    reset();
  }, [reset]);

  /**
   * Handles error dismissal.
   */
  const handleDismissError = React.useCallback(() => {
    reset();
  }, [reset]);

  // Show error state
  if (state.status === "error" && state.error) {
    return (
      <div className={cn("w-full", className)}>
        <UploadError
          error={state.error}
          onRetry={handleRetry}
          onDismiss={handleDismissError}
        />
      </div>
    );
  }

  // Show progress during upload
  if (state.status === "uploading" && state.filename) {
    return (
      <div className={cn("w-full", className)}>
        <UploadProgress
          progress={state.progress}
          filename={state.filename}
          bytesUploadedFormatted={bytesUploadedFormatted}
          bytesTotalFormatted={bytesTotalFormatted}
          onCancel={cancelUpload}
        />
      </div>
    );
  }

  // Show completion state briefly
  if (state.status === "complete" && state.filename) {
    return (
      <div className={cn("w-full", className)}>
        <UploadProgress
          progress={100}
          filename={state.filename}
          bytesUploadedFormatted={bytesTotalFormatted}
          bytesTotalFormatted={bytesTotalFormatted}
          isComplete
        />
      </div>
    );
  }

  // Show file selected state (ready to upload)
  if (state.filename && state.status === "idle") {
    return (
      <div className={cn("w-full", className)}>
        <div className="rounded-lg border bg-card p-6 shadow-sm">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
              <FileArchive className="h-6 w-6 text-primary" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate" title={state.filename}>
                {state.filename}
              </p>
              <p className="text-sm text-muted-foreground">
                {bytesTotalFormatted}
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={reset}>
                Change
              </Button>
              <Button size="sm" onClick={startUpload}>
                Upload
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Show drag-and-drop zone (default state)
  return (
    <div className={cn("w-full", className)}>
      <div
        className={cn(
          "relative rounded-lg border-2 border-dashed transition-colors",
          isDragOver
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-muted-foreground/50",
          disabled && "opacity-50 cursor-not-allowed"
        )}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".zip,application/zip,application/x-zip-compressed"
          onChange={handleFileInputChange}
          className="hidden"
          disabled={disabled}
          aria-label="Choose file to upload"
        />

        <div className="flex flex-col items-center justify-center py-12 px-6 text-center">
          <div
            className={cn(
              "flex h-14 w-14 items-center justify-center rounded-full mb-4",
              isDragOver ? "bg-primary/10" : "bg-muted"
            )}
          >
            <Upload
              className={cn(
                "h-6 w-6",
                isDragOver ? "text-primary" : "text-muted-foreground"
              )}
            />
          </div>

          <h3 className="text-lg font-semibold mb-1">
            {isDragOver
              ? "Drop your file here"
              : "Upload your TikTok export"}
          </h3>

          <p className="text-sm text-muted-foreground mb-4 max-w-sm">
            Drag and drop your TikTok data export ZIP file here, or click to
            browse
          </p>

          <Button
            variant="secondary"
            onClick={handleBrowseClick}
            disabled={disabled}
          >
            Browse Files
          </Button>

          <p className="text-xs text-muted-foreground mt-4">
            ZIP files only, max {formatBytes(maxFileSize)}
          </p>
        </div>
      </div>
    </div>
  );
}
