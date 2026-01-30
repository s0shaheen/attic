"use client";

/**
 * Upload summary component.
 *
 * Displays a summary of the upload including total items,
 * tier limit comparison, and estimated processing time.
 */

import * as React from "react";
import { Clock, CheckCircle, AlertCircle } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Props for the UploadSummary component.
 */
export interface UploadSummaryProps {
  /** Total items to process */
  totalItems: number;
  /** User's tier limit */
  tierLimit: number;
  /** Estimated processing time in minutes */
  estimatedMinutes: number;
  /** Whether within tier limit */
  withinLimit: boolean;
  /** Custom class name */
  className?: string;
}

/**
 * Format minutes into a human-readable string.
 */
function formatTime(minutes: number): string {
  if (minutes < 1) {
    return "Less than a minute";
  }
  if (minutes === 1) {
    return "About 1 minute";
  }
  if (minutes < 60) {
    return `About ${Math.round(minutes)} minutes`;
  }
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = Math.round(minutes % 60);
  if (hours === 1) {
    return remainingMinutes > 0
      ? `About 1 hour ${remainingMinutes} minutes`
      : "About 1 hour";
  }
  return remainingMinutes > 0
    ? `About ${hours} hours ${remainingMinutes} minutes`
    : `About ${hours} hours`;
}

/**
 * Upload summary component.
 *
 * Features:
 * - Shows total items to be processed
 * - Shows tier limit and comparison
 * - Shows estimated processing time
 * - Visual indicator for within/over limit
 *
 * @example
 * ```tsx
 * <UploadSummary
 *   totalItems={450}
 *   tierLimit={500}
 *   estimatedMinutes={15}
 *   withinLimit={true}
 * />
 * ```
 */
export function UploadSummary({
  totalItems,
  tierLimit,
  estimatedMinutes,
  withinLimit,
  className,
}: UploadSummaryProps) {
  const itemsToProcess = Math.min(totalItems, tierLimit);
  const percentUsed = Math.round((itemsToProcess / tierLimit) * 100);

  return (
    <div
      className={cn(
        "rounded-lg border bg-card p-4",
        className
      )}
    >
      <div className="space-y-4">
        {/* Items count */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Videos to analyze</span>
          <div className="flex items-center gap-2">
            {withinLimit ? (
              <CheckCircle className="h-4 w-4 text-green-600" />
            ) : (
              <AlertCircle className="h-4 w-4 text-amber-600" />
            )}
            <span className="font-medium">
              {itemsToProcess.toLocaleString()}
              {!withinLimit && (
                <span className="text-muted-foreground">
                  {" "}
                  / {totalItems.toLocaleString()} selected
                </span>
              )}
            </span>
          </div>
        </div>

        {/* Tier usage bar */}
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Tier usage</span>
            <span>
              {itemsToProcess.toLocaleString()} / {tierLimit.toLocaleString()}
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-500",
                withinLimit ? "bg-primary" : "bg-amber-500"
              )}
              style={{ width: `${Math.min(percentUsed, 100)}%` }}
            />
          </div>
        </div>

        {/* Estimated time */}
        <div className="flex items-center justify-between border-t pt-4">
          <span className="text-sm text-muted-foreground">Estimated time</span>
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">{formatTime(estimatedMinutes)}</span>
          </div>
        </div>

        {/* Note about leaving */}
        <p className="text-xs text-muted-foreground">
          You can leave this page while processing. We&apos;ll email you when
          it&apos;s done.
        </p>
      </div>
    </div>
  );
}

export default UploadSummary;
