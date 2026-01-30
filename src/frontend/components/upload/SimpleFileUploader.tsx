"use client";

/**
 * Simple file uploader component.
 *
 * A basic file uploader for ZIP files that will be replaced by the
 * full Uppy-based TikTokUploader component in Task 2.3.
 *
 * This component provides:
 * - Drag and drop support
 * - File picker
 * - File type validation (ZIP only)
 * - File size validation (500MB max)
 * - Progress indicator
 */

import * as React from "react";
import { Upload, FileArchive, X, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Result from file upload.
 */
export interface UploadResult {
  uploadId: string;
  storagePath: string;
  filename: string;
}

/**
 * Props for the SimpleFileUploader component.
 */
export interface SimpleFileUploaderProps {
  /** Called when upload completes successfully */
  onUploadComplete: (result: UploadResult) => void;
  /** Called when upload fails */
  onUploadError?: (error: Error) => void;
  /** Called when upload is cancelled */
  onUploadCancel?: () => void;
  /** Called when upload starts */
  onUploadStart?: () => void;
  /** Maximum file size in bytes (default: 500MB) */
  maxFileSize?: number;
  /** Whether the uploader is disabled */
  disabled?: boolean;
  /** Custom class name for styling */
  className?: string;
}

/**
 * Allowed MIME types for ZIP files.
 */
const ALLOWED_MIME_TYPES = [
  "application/zip",
  "application/x-zip-compressed",
  "application/octet-stream",
];

/**
 * Default max file size: 500MB.
 */
const DEFAULT_MAX_SIZE = 500 * 1024 * 1024;

/**
 * Format bytes to human readable string.
 */
function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

/**
 * Upload state.
 */
type UploadState = "idle" | "selected" | "uploading" | "error";

/**
 * Simple file uploader component.
 *
 * A placeholder uploader until the full Uppy integration is complete.
 * Supports drag and drop, file validation, and basic progress indication.
 *
 * @example
 * ```tsx
 * <SimpleFileUploader
 *   onUploadComplete={handleComplete}
 *   onUploadError={handleError}
 * />
 * ```
 */
export function SimpleFileUploader({
  onUploadComplete,
  onUploadError,
  onUploadCancel,
  onUploadStart,
  maxFileSize = DEFAULT_MAX_SIZE,
  disabled = false,
  className,
}: SimpleFileUploaderProps) {
  const [state, setState] = React.useState<UploadState>("idle");
  const [selectedFile, setSelectedFile] = React.useState<File | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [isDragOver, setIsDragOver] = React.useState(false);
  const [progress, setProgress] = React.useState(0);

  const fileInputRef = React.useRef<HTMLInputElement>(null);

  /**
   * Validate a file before upload.
   */
  const validateFile = React.useCallback(
    (file: File): string | null => {
      // Check file extension
      if (!file.name.toLowerCase().endsWith(".zip")) {
        return "Please upload a ZIP file";
      }

      // Check MIME type (but allow octet-stream as fallback)
      if (
        !ALLOWED_MIME_TYPES.includes(file.type) &&
        file.type !== ""
      ) {
        return "Please upload a valid ZIP file";
      }

      // Check file size
      if (file.size > maxFileSize) {
        return `File is too large. Maximum size is ${formatBytes(maxFileSize)}`;
      }

      return null;
    },
    [maxFileSize]
  );

  /**
   * Handle file selection (from input or drop).
   */
  const handleFileSelect = React.useCallback(
    (file: File) => {
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        setState("error");
        onUploadError?.(new Error(validationError));
        return;
      }

      setSelectedFile(file);
      setError(null);
      setState("selected");
    },
    [validateFile, onUploadError]
  );

  /**
   * Handle file input change.
   */
  const handleInputChange = React.useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        handleFileSelect(file);
      }
    },
    [handleFileSelect]
  );

  /**
   * Handle drag events.
   */
  const handleDragEnter = React.useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = React.useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDragOver = React.useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = React.useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);

      const file = e.dataTransfer.files?.[0];
      if (file) {
        handleFileSelect(file);
      }
    },
    [handleFileSelect]
  );

  /**
   * Start the upload.
   */
  const handleUpload = React.useCallback(async () => {
    if (!selectedFile) return;

    setState("uploading");
    setProgress(0);
    onUploadStart?.();

    try {
      // Simulate getting a presigned URL (to be replaced with actual API call)
      // In the real implementation, this would call the presigned URL API
      setProgress(10);

      // Simulate upload progress
      const progressInterval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 10;
        });
      }, 200);

      // Simulate upload completion
      // In the real implementation, this would:
      // 1. Call POST /api/uploads/presigned-url
      // 2. Upload file to the presigned URL
      // 3. Return the upload_id and storage_path
      await new Promise((resolve) => setTimeout(resolve, 2000));

      clearInterval(progressInterval);
      setProgress(100);

      // Generate mock result (to be replaced with real API response)
      const mockResult: UploadResult = {
        uploadId: crypto.randomUUID(),
        storagePath: `uploads/${Date.now()}/${selectedFile.name}`,
        filename: selectedFile.name,
      };

      onUploadComplete(mockResult);
    } catch (err) {
      setState("error");
      const error =
        err instanceof Error ? err : new Error("Upload failed");
      setError(error.message);
      onUploadError?.(error);
    }
  }, [selectedFile, onUploadComplete, onUploadError, onUploadStart]);

  /**
   * Cancel the upload.
   */
  const handleCancel = React.useCallback(() => {
    setSelectedFile(null);
    setState("idle");
    setError(null);
    setProgress(0);
    onUploadCancel?.();
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, [onUploadCancel]);

  /**
   * Open file picker.
   */
  const openFilePicker = React.useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  return (
    <div className={cn("w-full", className)}>
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".zip,application/zip,application/x-zip-compressed"
        onChange={handleInputChange}
        className="hidden"
        disabled={disabled || state === "uploading"}
      />

      {/* Drop zone */}
      <div
        className={cn(
          "relative flex min-h-[200px] flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 transition-colors",
          isDragOver && "border-primary bg-primary/5",
          state === "error" && "border-destructive bg-destructive/5",
          disabled
            ? "cursor-not-allowed opacity-50"
            : "cursor-pointer hover:border-primary/50 hover:bg-accent/50",
          state === "uploading" && "pointer-events-none"
        )}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => state === "idle" && !disabled && openFilePicker()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (
            (e.key === "Enter" || e.key === " ") &&
            state === "idle" &&
            !disabled
          ) {
            e.preventDefault();
            openFilePicker();
          }
        }}
        aria-label="Upload zone"
      >
        {/* Idle state */}
        {state === "idle" && !error && (
          <>
            <Upload className="h-12 w-12 text-muted-foreground" />
            <p className="mt-4 text-lg font-medium">
              Drop your TikTok export here
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              or click to select a file
            </p>
            <p className="mt-3 text-xs text-muted-foreground">
              ZIP files only, max {formatBytes(maxFileSize)}
            </p>
          </>
        )}

        {/* Selected state */}
        {state === "selected" && selectedFile && (
          <div className="flex flex-col items-center gap-4">
            <FileArchive className="h-12 w-12 text-primary" />
            <div className="text-center">
              <p className="font-medium">{selectedFile.name}</p>
              <p className="text-sm text-muted-foreground">
                {formatBytes(selectedFile.size)}
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleCancel}>
                <X className="mr-2 h-4 w-4" />
                Cancel
              </Button>
              <Button size="sm" onClick={handleUpload}>
                <Upload className="mr-2 h-4 w-4" />
                Upload
              </Button>
            </div>
          </div>
        )}

        {/* Uploading state */}
        {state === "uploading" && (
          <div className="flex flex-col items-center gap-4">
            <Loader2 className="h-12 w-12 animate-spin text-primary" />
            <div className="text-center">
              <p className="font-medium">Uploading...</p>
              <p className="text-sm text-muted-foreground">{progress}%</p>
            </div>
            <div className="h-2 w-48 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Error state */}
        {state === "error" && error && (
          <div className="flex flex-col items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
              <X className="h-6 w-6 text-destructive" />
            </div>
            <div className="text-center">
              <p className="font-medium text-destructive">{error}</p>
            </div>
            <Button variant="outline" size="sm" onClick={handleCancel}>
              Try again
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

export default SimpleFileUploader;
