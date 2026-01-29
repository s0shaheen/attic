/**
 * Next.js middleware for Supabase session management.
 *
 * Runs on every request to refresh expired access tokens automatically.
 * This ensures users don't get logged out unexpectedly when their
 * access token expires (default 1 hour).
 */

import { type NextRequest } from "next/server"
import { createClient } from "@/lib/supabase/middleware"

export async function middleware(request: NextRequest) {
  // Create Supabase client and refresh session if needed
  const { response } = await createClient(request)

  // Return response with any updated cookies
  return response
}

/**
 * Configure which routes the middleware runs on.
 * Excludes static assets and files to improve performance.
 */
export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - Public files with extensions (images, fonts, etc.)
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|woff|woff2|ttf|eot)$).*)",
  ],
}
