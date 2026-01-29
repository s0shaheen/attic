import { createClient } from "@/lib/supabase/server"
import { NextResponse } from "next/server"

/**
 * Server-side sign out route handler.
 *
 * Handles POST requests to sign out the current user:
 * 1. Calls Supabase to clear session/cookies
 * 2. Logs the event server-side
 * 3. Redirects to login page
 *
 * Note: Even if Supabase call fails, we still redirect to login.
 * This ensures users can always "sign out" even in degraded conditions.
 */
export async function POST(request: Request) {
  const supabase = await createClient()

  // Get user ID for logging before sign out (optional, for analytics)
  const {
    data: { user },
  } = await supabase.auth.getUser()

  const { error } = await supabase.auth.signOut()

  if (error) {
    // Log error but still redirect to login
    console.error("[auth_signout]", {
      event: "signout_error",
      user_id: user?.id ?? "unknown",
      error_type: error.name,
    })
  } else {
    // Log successful sign out
    console.log("[auth_signout]", {
      event: "user_signed_out",
      user_id: user?.id ?? "unknown",
    })
  }

  // Always redirect to login - user should end up signed out regardless
  return NextResponse.redirect(new URL("/auth/login", request.url))
}

/**
 * GET handler - redirect to POST or show error.
 *
 * Sign out should be a POST action, but if someone navigates here directly,
 * we redirect them to login.
 */
export async function GET(request: Request) {
  return NextResponse.redirect(new URL("/auth/login", request.url))
}
