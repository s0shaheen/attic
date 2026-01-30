"use client";

/**
 * Upload error display component.
 *
 * Shows upload error messages with retry and dismiss options.
 */

import * as React from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { AlertCircle, RotateCcw, X } from "lucide-react";

export interface UploadErrorProps {
  /** Error object containing the error message */
  error: Error;
  /** Callback when retry button is clicked */
  onRetry?: () => void;
  /** Callback when dismiss button is clicked */
  onDismiss?: () => void;
  /** Custom class name */
  className?: string;
}

/**
 * User-friendly error messages for common upload errors.
 */
function getErrorMessage(error: Error): string {
  const message = error.message.toLowerCase();

  // File type errors
  if (message.includes("file type") || message.includes("allowed type") || message.includes("must be a zip")) {
    return "Please select a ZIP file. Only .zip files from TikTok exports are supported.";
  }

  // File size errors
  if (message.includes("file size") || message.includes("too large") || message.includes("exceeds")) {
    return "This file is too large. Maximum file size is 500MB.";
  }

  // Authentication errors
  if (message.includes("authenticated") || message.includes("sign in") || message.includes("unauthorized")) {
    return "Please sign in to upload files.";
  }

  // Upload limit errors
  if (message.includes("limit") || message.includes("exceeded") || message.includes("quota")) {
    return "You have reached your upload limit. Please upgrade your plan or delete existing uploads.";
  }

  // Network errors
  if (message.includes("network") || message.includes("connection") || message.includes("offline")) {
    return "Network error. Please check your internet connection and try again.";
  }

  // Timeout errors
  if (message.includes("timeout") || message.includes("timed out")) {
    return "Upload timed out. Please try again with a stable connection.";
  }

  // API URL not configured
  if (message.includes("api url not configured")) {
    return "Upload service is not configured. Please contact support.";
  }

  // Default to original message if no match
  return error.message || "An unexpected error occurred. Please try again.";
}

/**
 * Displays upload errors with user-friendly messages.
 *
 * Features:
 * - Clear error icon and message
 * - Retry button
 * - Dismiss button
 * - User-friendly error message mapping
 *
 * @example
 * ```tsx
 * <UploadError
 *   error={new Error("File type not allowed")}
 *   onRetry={() => handleRetry()}
 *   onDismiss={() => handleDismiss()}
 * />
 * ```
 */
export function UploadError({
  error,
  onRetry,
  onDismiss,
  className,
}: UploadErrorProps) {
  const friendlyMessage = getErrorMessage(error);

  return (
    <div
      className={cn(
        "w-full rounded-lg border border-destructive/50 bg-destructive/10 p-4",
        className
      )}
      role="alert"
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-medium text-destructive">
            Upload Failed
          </h4>
          <p className="mt-1 text-sm text-muted-foreground">
            {friendlyMessage}
          </p>
        </div>
        {onDismiss && (
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-foreground flex-shrink-0"
            onClick={onDismiss}
            aria-label="Dismiss error"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {onRetry && (
        <div className="mt-3 flex justify-end">
          <Button
            variant="outline"
            size="sm"
            onClick={onRetry}
            className="gap-2"
          >
            <RotateCcw className="h-4 w-4" />
            Try Again
          </Button>
        </div>
      )}
    </div>
  );
}
