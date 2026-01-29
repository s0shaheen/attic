/**
 * Middleware Supabase client for session refresh.
 *
 * Creates a Supabase client specifically for use in Next.js middleware,
 * with read/write access to request/response cookies for token refresh.
 */

import { createServerClient } from "@supabase/ssr"
import { NextResponse, type NextRequest } from "next/server"

/**
 * Creates a Supabase client for middleware context with cookie handling.
 * Automatically refreshes the session if the access token is expired.
 *
 * @param request - The incoming Next.js request
 * @returns Object containing the Supabase client and the response with updated cookies
 */
export async function createClient(request: NextRequest) {
  // Create a response that we can modify
  let supabaseResponse = NextResponse.next({
    request,
  })

  // Skip Supabase client creation if env vars are not available (e.g., during CI build)
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!supabaseUrl || !supabaseAnonKey) {
    return { supabase: null, response: supabaseResponse }
  }

  const supabase = createServerClient(
    supabaseUrl,
    supabaseAnonKey,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          // Set cookies on request for downstream handlers
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          )
          // Create new response with updated cookies
          supabaseResponse = NextResponse.next({
            request,
          })
          // Set cookies on response to persist in browser
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  // Refresh session if expired - getUser() validates the token
  // and refreshes it if necessary, updating cookies automatically
  await supabase.auth.getUser()

  return { supabase, response: supabaseResponse }
}
