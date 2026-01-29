"use client"

import * as React from "react"
import { AlertCircle, X } from "lucide-react"
import { cn } from "@/lib/utils"

export interface AuthErrorProps {
  /** The error message to display */
  message: string | null
  /** Optional callback when the error is dismissed */
  onDismiss?: () => void
  /** Optional className */
  className?: string
}

/**
 * Maps error codes/messages to user-friendly text.
 * Sanitizes technical error messages for display.
 */
function getUserFriendlyMessage(message: string): string {
  const lowerMessage = message.toLowerCase()

  // Access denied by user
  if (
    lowerMessage.includes("access_denied") ||
    lowerMessage.includes("user denied") ||
    lowerMessage.includes("consent_required")
  ) {
    return "You need to grant permission to sign in. Please try again."
  }

  // Network/connection errors
  if (
    lowerMessage.includes("network") ||
    lowerMessage.includes("connection") ||
    lowerMessage.includes("timeout")
  ) {
    return "Unable to connect. Please check your internet connection and try again."
  }

  // Session/token errors
  if (
    lowerMessage.includes("session") ||
    lowerMessage.includes("expired") ||
    lowerMessage.includes("invalid")
  ) {
    return "Your session has expired. Please try signing in again."
  }

  // Service unavailable
  if (
    lowerMessage.includes("unavailable") ||
    lowerMessage.includes("service")
  ) {
    return "The authentication service is temporarily unavailable. Please try again later."
  }

  // Generic authentication failure
  if (lowerMessage.includes("authentication failed")) {
    return "Unable to sign in. Please try again."
  }

  // Default: show a sanitized version of the message
  // Remove any potential PII or technical details
  return "An error occurred during sign in. Please try again."
}

/**
 * Component to display authentication errors.
 * Shows user-friendly error messages with dismiss functionality.
 * Styled with warm, non-alarming colors to match the design system.
 */
export function AuthError({ message, onDismiss, className }: AuthErrorProps) {
  if (!message) {
    return null
  }

  const friendlyMessage = getUserFriendlyMessage(message)

  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm",
        className
      )}
    >
      <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-600" />
      <div className="flex-1">
        <p className="text-red-800">{friendlyMessage}</p>
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="rounded-md p-1 text-red-600 hover:bg-red-100 hover:text-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
          aria-label="Dismiss error"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}
