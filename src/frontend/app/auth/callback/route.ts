import { createClient } from "@/lib/supabase/server"
import { NextResponse } from "next/server"

/**
 * OAuth callback handler.
 *
 * Handles the redirect from Google OAuth:
 * 1. Extracts the authorization code from URL
 * 2. Exchanges code for session via Supabase
 * 3. Redirects to app on success, login on failure
 *
 * This route is called after Google redirects back with:
 * - ?code=xxx (on success)
 * - ?error=xxx&error_description=xxx (on failure)
 */
export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get("code")
  const error = searchParams.get("error")
  const errorDescription = searchParams.get("error_description")

  // Handle OAuth error from provider
  if (error) {
    const errorMessage = errorDescription || error
    return NextResponse.redirect(
      `${origin}/auth/login?error=${encodeURIComponent(errorMessage)}`
    )
  }

  // No code present - something went wrong
  if (!code) {
    return NextResponse.redirect(
      `${origin}/auth/login?error=${encodeURIComponent("Authentication failed - no authorization code received")}`
    )
  }

  // Exchange code for session
  const supabase = await createClient()
  const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code)

  if (exchangeError) {
    // Log server-side for debugging (no PII)
    console.error("[auth_callback]", {
      event: "code_exchange_failed",
      error_type: exchangeError.name,
    })

    return NextResponse.redirect(
      `${origin}/auth/login?error=${encodeURIComponent("Authentication failed - please try again")}`
    )
  }

  // Success - redirect to main app
  return NextResponse.redirect(`${origin}/library`)
}
