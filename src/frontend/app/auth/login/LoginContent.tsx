"use client"

import * as React from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { GoogleSignInButton } from "@/components/auth/GoogleSignInButton"
import { AuthError } from "@/components/auth/AuthError"

interface LoginContentProps {
  error: string | null
}

/**
 * Login page content - Client Component.
 *
 * Handles:
 * - Google sign-in button interaction
 * - Error display from URL params
 * - Error dismissal
 */
export function LoginContent({ error: initialError }: LoginContentProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [error, setError] = React.useState<string | null>(initialError)

  // Sync error state with URL params
  React.useEffect(() => {
    const urlError = searchParams.get("error")
    if (urlError) {
      setError(urlError)
    }
  }, [searchParams])

  function handleDismissError() {
    setError(null)
    // Clear error from URL without navigation
    router.replace("/auth/login", { scroll: false })
  }

  function handleSignInError(err: Error) {
    setError(err.message)
  }

  return (
    <main className="min-h-screen bg-background flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-md space-y-8">
        {/* Logo and branding */}
        <div className="text-center">
          <h1 className="text-4xl font-bold text-foreground tracking-tight">
            Attic
          </h1>
          <p className="mt-2 text-muted-foreground">
            Personal analytics for your TikTok data
          </p>
        </div>

        {/* Login card */}
        <Card className="shadow-lg">
          <CardHeader className="text-center pb-2">
            <CardTitle className="text-xl">Welcome back</CardTitle>
            <CardDescription>
              Sign in to continue to your dashboard
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 pt-4">
            {/* Error display */}
            {error && (
              <AuthError message={error} onDismiss={handleDismissError} />
            )}

            {/* Sign in button */}
            <GoogleSignInButton
              onError={handleSignInError}
              className="w-full"
            />

            {/* Privacy note */}
            <p className="text-xs text-center text-muted-foreground pt-2">
              By signing in, you agree to our terms of service and privacy policy.
              We only access basic profile information.
            </p>
          </CardContent>
        </Card>

        {/* Footer */}
        <p className="text-center text-sm text-muted-foreground">
          Don&apos;t have an account? Signing in will create one automatically.
        </p>
      </div>
    </main>
  )
}
