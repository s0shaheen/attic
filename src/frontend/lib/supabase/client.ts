/**
 * Browser Supabase client for client components.
 *
 * Uses the @supabase/ssr package to create a client that automatically
 * handles cookie-based session management.
 */

import { createBrowserClient } from "@supabase/ssr"
import type { SupabaseClient } from "@supabase/supabase-js"

/**
 * Creates a Supabase client for use in browser/client components.
 * Sessions are stored in HTTP-only cookies via the @supabase/ssr package.
 *
 * @returns A Supabase client, or null if environment variables are not configured
 */
export function createClient(): SupabaseClient | null {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  // During build time (CI), env vars may not be available
  // Return null to allow build to complete
  if (!supabaseUrl || !supabaseAnonKey) {
    return null
  }

  return createBrowserClient(supabaseUrl, supabaseAnonKey)
}
