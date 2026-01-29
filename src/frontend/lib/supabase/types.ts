/**
 * Type definitions for Supabase authentication state.
 */

import type { User, Session } from "@supabase/supabase-js"

/**
 * Represents the current authentication state.
 */
export interface AuthState {
  user: User | null
  session: Session | null
  isLoading: boolean
}

/**
 * Return type for the useUser hook.
 */
export interface UseUserReturn {
  user: User | null
  isLoading: boolean
  error: Error | null
}
