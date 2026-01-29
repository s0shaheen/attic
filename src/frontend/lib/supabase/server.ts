/**
 * Server Supabase client for Server Components, Server Actions, and Route Handlers.
 *
 * Uses the @supabase/ssr package with cookie handling for session management.
 * Must be called within a Server Component or server context.
 */

import { createServerClient } from "@supabase/ssr"
import { cookies } from "next/headers"

/**
 * Creates a Supabase client for use in server contexts.
 * Handles cookie-based session management with automatic refresh.
 *
 * @returns A Supabase client configured for server-side use
 * @throws Error if Supabase environment variables are not configured
 */
export async function createClient() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error(
      "Missing Supabase environment variables. " +
        "Please set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY."
    )
  }

  const cookieStore = await cookies()

  return createServerClient(
    supabaseUrl,
    supabaseAnonKey,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            )
          } catch {
            // Called from Server Component where cookies cannot be set.
            // This is expected in Server Components (read-only context).
          }
        },
      },
    }
  )
}

/**
 * Gets the current user from the server session.
 * Returns null if no authenticated user.
 *
 * @returns The current user or null
 */
export async function getUser() {
  const supabase = await createClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()
  return user
}

/**
 * Gets the current session from the server.
 * Returns null if no active session.
 *
 * @returns The current session or null
 */
export async function getSession() {
  const supabase = await createClient()
  const {
    data: { session },
  } = await supabase.auth.getSession()
  return session
}
