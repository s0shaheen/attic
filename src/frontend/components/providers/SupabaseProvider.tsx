"use client"

/**
 * Supabase Auth Context Provider.
 *
 * Provides auth state to the entire application via React Context.
 * Handles auth state changes and provides user info to child components.
 */

import { createContext, useContext, useState, useEffect, useMemo } from "react"
import type { User, Session, SupabaseClient, AuthChangeEvent } from "@supabase/supabase-js"
import { createClient } from "@/lib/supabase/client"
import type { AuthState } from "@/lib/supabase/types"

interface SupabaseContextValue extends AuthState {
  supabase: SupabaseClient | null
}

const SupabaseContext = createContext<SupabaseContextValue | undefined>(
  undefined
)

interface SupabaseProviderProps {
  children: React.ReactNode
}

/**
 * Provider component that wraps the app to provide Supabase auth state.
 *
 * @example
 * ```tsx
 * // In your root layout
 * export default function RootLayout({ children }) {
 *   return (
 *     <html>
 *       <body>
 *         <SupabaseProvider>
 *           {children}
 *         </SupabaseProvider>
 *       </body>
 *     </html>
 *   )
 * }
 * ```
 */
export function SupabaseProvider({ children }: SupabaseProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Create client once and memoize (may be null during build)
  const supabase = useMemo(() => createClient(), [])

  useEffect(() => {
    // Skip if Supabase client not available (e.g., during build)
    if (!supabase) {
      setIsLoading(false)
      return
    }

    // Get initial session
    async function getInitialSession() {
      const {
        data: { session: initialSession },
      } = await supabase!.auth.getSession()

      setSession(initialSession)
      setUser(initialSession?.user ?? null)
      setIsLoading(false)
    }

    getInitialSession()

    // Subscribe to auth state changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event: AuthChangeEvent, newSession: Session | null) => {
      setSession(newSession)
      setUser(newSession?.user ?? null)
      setIsLoading(false)
    })

    return () => {
      subscription.unsubscribe()
    }
  }, [supabase])

  const value = useMemo(
    () => ({
      supabase,
      user,
      session,
      isLoading,
    }),
    [supabase, user, session, isLoading]
  )

  return (
    <SupabaseContext.Provider value={value}>
      {children}
    </SupabaseContext.Provider>
  )
}

/**
 * Hook to access the Supabase context.
 *
 * @returns The Supabase context value including client and auth state
 * @throws Error if used outside of SupabaseProvider
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { supabase, user, isLoading } = useSupabase()
 *
 *   if (isLoading) return <div>Loading...</div>
 *   if (!user) return <div>Not logged in</div>
 *
 *   return <div>Welcome, {user.email}</div>
 * }
 * ```
 */
export function useSupabase(): SupabaseContextValue {
  const context = useContext(SupabaseContext)

  if (context === undefined) {
    throw new Error("useSupabase must be used within a SupabaseProvider")
  }

  return context
}
