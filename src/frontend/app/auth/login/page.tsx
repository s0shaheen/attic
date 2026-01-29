import { redirect } from "next/navigation"
import { createClient } from "@/lib/supabase/server"
import { LoginContent } from "./LoginContent"

// Prevent static prerendering - this page needs runtime auth check
export const dynamic = "force-dynamic"

export const metadata = {
  title: "Sign In - Attic",
  description: "Sign in to Attic to access your TikTok analytics",
}

/**
 * Login page - Server Component.
 *
 * Checks if user is already authenticated and redirects to app.
 * Otherwise renders the login UI.
 */
export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>
}) {
  // Check for existing session
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  // If authenticated, redirect to main app
  if (user) {
    redirect("/library")
  }

  const params = await searchParams
  const error = params.error || null

  return <LoginContent error={error} />
}
