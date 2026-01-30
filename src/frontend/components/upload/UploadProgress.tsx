"use client";

/**
 * Upload progress display component.
 *
 * Shows upload progress with a progress bar, percentage,
 * bytes uploaded/total, and a cancel button.
 */

import * as React from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { X, Loader2 } from "lucide-react";

export interface UploadProgressProps {
  /** Upload progress percentage (0-100) */
  progress: number;
  /** Filename being uploaded */
  filename: string;
  /** Formatted bytes uploaded (e.g., "45.5 MB") */
  bytesUploadedFormatted: string;
  /** Formatted total bytes (e.g., "100 MB") */
  bytesTotalFormatted: string;
  /** Whether upload is complete */
  isComplete?: boolean;
  /** Callback when cancel button is clicked */
  onCancel?: () => void;
  /** Custom class name */
  className?: string;
}

/**
 * Displays upload progress with visual feedback.
 *
 * Features:
 * - Progress bar with percentage
 * - Bytes uploaded / total display
 * - Filename display
 * - Cancel button (hidden when complete)
 * - Completion state with checkmark
 *
 * @example
 * ```tsx
 * <UploadProgress
 *   progress={45}
 *   filename="my-tiktok-export.zip"
 *   bytesUploadedFormatted="45 MB"
 *   bytesTotalFormatted="100 MB"
 *   onCancel={() => handleCancel()}
 * />
 * ```
 */
export function UploadProgress({
  progress,
  filename,
  bytesUploadedFormatted,
  bytesTotalFormatted,
  isComplete = false,
  onCancel,
  className,
}: UploadProgressProps) {
  const clampedProgress = Math.min(100, Math.max(0, progress));

  return (
    <div
      className={cn(
        "w-full rounded-lg border bg-card p-4 shadow-sm",
        className
      )}
    >
      {/* Header with filename and cancel button */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          {isComplete ? (
            <div className="flex h-5 w-5 items-center justify-center rounded-full bg-green-100 text-green-600">
              <svg
                className="h-3 w-3"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={3}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
          ) : (
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          )}
          <span className="text-sm font-medium truncate" title={filename}>
            {filename}
          </span>
        </div>

        {!isComplete && onCancel && (
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={onCancel}
            aria-label="Cancel upload"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Progress bar */}
      <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
        <div
          className={cn(
            "h-full transition-all duration-300 ease-out rounded-full",
            isComplete ? "bg-green-500" : "bg-primary"
          )}
          style={{ width: `${clampedProgress}%` }}
          role="progressbar"
          aria-valuenow={clampedProgress}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Upload progress: ${clampedProgress}%`}
        />
      </div>

      {/* Progress details */}
      <div className="flex items-center justify-between mt-2 text-sm text-muted-foreground">
        <span>
          {bytesUploadedFormatted} / {bytesTotalFormatted}
        </span>
        <span className="font-medium">
          {isComplete ? "Complete" : `${clampedProgress}%`}
        </span>
      </div>
    </div>
  );
}
