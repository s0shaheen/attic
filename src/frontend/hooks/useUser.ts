"use client"

/**
 * React hook for accessing the current authenticated user.
 *
 * Provides the current user, loading state, and any errors.
 * Automatically updates when the auth state changes.
 */

import { useState, useEffect } from "react"
import type { User, Session, AuthChangeEvent } from "@supabase/supabase-js"
import { createClient } from "@/lib/supabase/client"
import type { UseUserReturn } from "@/lib/supabase/types"

/**
 * Hook to access the current authenticated user.
 *
 * @returns Object containing user, loading state, and error
 *
 * @example
 * ```tsx
 * function Profile() {
 *   const { user, isLoading, error } = useUser()
 *
 *   if (isLoading) return <div>Loading...</div>
 *   if (error) return <div>Error: {error.message}</div>
 *   if (!user) return <div>Not logged in</div>
 *
 *   return <div>Hello, {user.email}</div>
 * }
 * ```
 */
export function useUser(): UseUserReturn {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    const supabase = createClient()

    // Skip if Supabase client not available (e.g., during build)
    if (!supabase) {
      setIsLoading(false)
      return
    }

    // Get initial user
    async function getUser() {
      try {
        const {
          data: { user },
          error: userError,
        } = await supabase!.auth.getUser()

        if (userError) {
          // PGRST301 means no session - not an error condition
          if (userError.message !== "Auth session missing!") {
            setError(new Error(userError.message))
          }
          setUser(null)
        } else {
          setUser(user)
        }
      } catch (err) {
        setError(err instanceof Error ? err : new Error("Failed to get user"))
      } finally {
        setIsLoading(false)
      }
    }

    getUser()

    // Subscribe to auth state changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event: AuthChangeEvent, session: Session | null) => {
      setUser(session?.user ?? null)
      setIsLoading(false)
      setError(null)
    })

    return () => {
      subscription.unsubscribe()
    }
  }, [])

  return { user, isLoading, error }
}
