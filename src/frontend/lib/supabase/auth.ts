/**
 * Supabase auth utility functions.
 *
 * Contains shared authentication operations like sign out
 * that can be used across the application.
 */

import { createClient } from "@/lib/supabase/client"

/**
 * Sign out result type.
 */
export interface SignOutResult {
  error: Error | null
}

/**
 * Signs out the current user from Supabase.
 *
 * This function handles errors gracefully - even if the Supabase call fails,
 * we attempt to clear local state and redirect. This ensures users can always
 * sign out, even in degraded conditions.
 *
 * @returns Promise with error field (null on success)
 */
export async function signOut(): Promise<SignOutResult> {
  try {
    const supabase = createClient()
    if (!supabase) {
      return { error: new Error("Supabase client not available") }
    }
    const { error } = await supabase.auth.signOut()

    if (error) {
      // Log error for debugging but don't throw - we still want to "sign out"
      console.error("[auth] Sign out error:", {
        event: "signout_error",
        error_type: error.name,
        error_message: error.message,
      })
      return { error }
    }

    return { error: null }
  } catch (err) {
    // Network or unexpected error - still return gracefully
    const error = err instanceof Error ? err : new Error("Sign out failed")
    console.error("[auth] Sign out exception:", {
      event: "signout_exception",
      error_message: error.message,
    })
    return { error }
  }
}
