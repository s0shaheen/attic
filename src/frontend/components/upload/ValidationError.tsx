"use client";

/**
 * Validation error display component.
 *
 * Shows validation error messages with user-friendly copy,
 * retry option, and help link.
 */

import * as React from "react";
import { AlertCircle, HelpCircle, RotateCcw, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  ERROR_MESSAGES,
  ValidationErrorCode,
  isValidationErrorCode,
} from "@/lib/errors/upload";

export interface ValidationErrorProps {
  /** The validation error code from the API */
  errorCode: ValidationErrorCode | string;
  /** Optional custom error message (overrides default) */
  errorMessage?: string | null;
  /** Callback when retry button is clicked */
  onRetry?: () => void;
  /** Callback when dismiss button is clicked */
  onDismiss?: () => void;
  /** Callback when help link is clicked */
  onHelp?: () => void;
  /** Custom class name */
  className?: string;
}

/**
 * Displays validation errors with user-friendly messages.
 *
 * Features:
 * - Mapped error codes to friendly messages
 * - Custom error message support
 * - Retry button
 * - Dismiss button
 * - Help link
 *
 * @example
 * ```tsx
 * <ValidationError
 *   errorCode="INVALID_EXPORT"
 *   onRetry={() => handleRetry()}
 *   onDismiss={() => handleDismiss()}
 * />
 * ```
 */
export function ValidationError({
  errorCode,
  errorMessage,
  onRetry,
  onDismiss,
  onHelp,
  className,
}: ValidationErrorProps) {
  // Get the error message from our mapping, or use fallback
  const errorInfo = isValidationErrorCode(errorCode)
    ? ERROR_MESSAGES[errorCode]
    : {
        title: "Validation failed",
        description: errorMessage || "An unexpected error occurred. Please try again.",
      };

  // Use custom message if provided
  const description = errorMessage || errorInfo.description;

  return (
    <div
      className={cn(
        "w-full rounded-lg border border-destructive/50 bg-destructive/10 p-4",
        className
      )}
      role="alert"
      aria-live="polite"
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-medium text-destructive">
            {errorInfo.title}
          </h4>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
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

      <div className="mt-3 flex items-center justify-between">
        {onHelp && (
          <Button
            variant="link"
            size="sm"
            className="gap-1 text-muted-foreground h-auto p-0"
            onClick={onHelp}
          >
            <HelpCircle className="h-3.5 w-3.5" />
            Need help?
          </Button>
        )}
        {!onHelp && <div />}

        {onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry} className="gap-2">
            <RotateCcw className="h-4 w-4" />
            Try Again
          </Button>
        )}
      </div>
    </div>
  );
}

export default ValidationError;
