"use client";

import { useAuth } from "@/lib/auth-context";
import { trackAuthEvent } from "@/lib/posthog";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

const isDev = process.env.NEXT_PUBLIC_ENVIRONMENT === "development";

/** Strip potential PII from Supabase error messages before sending to analytics. */
function sanitizeErrorForAnalytics(message: string): string {
  // Replace anything that looks like an email with [REDACTED]
  return message.replace(/[^\s@]+@[^\s@]+\.[^\s@]+/g, "[REDACTED]");
}

function LoginForm() {
  const { user, supabase } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextParam = searchParams.get("next");
  const messageParam = searchParams.get("message");

  const [mode, setMode] = useState<"signin" | "signup" | "forgot">("signin");
  const [email, setEmail] = useState(isDev ? "test@attic.dev" : "");
  const [password, setPassword] = useState(isDev ? "testtest123" : "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  // Sanitize redirect target
  const redirectTo =
    nextParam && nextParam.startsWith("/") && !nextParam.includes("://")
      ? nextParam
      : "/chat";

  // Redirect if already authenticated
  useEffect(() => {
    if (user) {
      router.replace(redirectTo);
    }
  }, [user, router, redirectTo]);

  async function handleEmailAuth(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;

    setLoading(true);
    setError(null);
    setInfo(null);

    if (mode === "forgot") {
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(
        email,
        { redirectTo: `${window.location.origin}/auth/reset-password` },
      );
      setLoading(false);
      if (resetError) {
        setError(resetError.message);
        trackAuthEvent("password_reset_failure", {
          reason: sanitizeErrorForAnalytics(resetError.message),
        });
      } else {
        setInfo("Check your email for a password reset link.");
        trackAuthEvent("password_reset_requested");
      }
      return;
    }

    if (mode === "signup") {
      const { error: signUpError } = await supabase.auth.signUp({
        email,
        password,
        options: {
          emailRedirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(redirectTo)}`,
        },
      });
      setLoading(false);
      if (signUpError) {
        if (signUpError.message.toLowerCase().includes("rate limit")) {
          setError("Too many attempts. Please try again in 60 seconds.");
        } else {
          setError(signUpError.message);
        }
        trackAuthEvent("signup_failure", { reason: sanitizeErrorForAnalytics(signUpError.message) });
      } else {
        trackAuthEvent("signup_success");
        // In dev, email confirm is disabled so onAuthStateChange will fire
        // In prod, redirect to verify page
        if (!isDev) {
          router.push("/auth/verify");
        }
      }
      return;
    }

    // Sign in
    const { error: signInError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    setLoading(false);
    if (signInError) {
      if (signInError.message.toLowerCase().includes("rate limit")) {
        setError("Too many attempts. Please try again in 60 seconds.");
      } else {
        setError("Invalid email or password.");
      }
      trackAuthEvent("login_failure", {
        reason: sanitizeErrorForAnalytics(signInError.message),
        method: "email",
      });
    } else {
      trackAuthEvent("login_success", { method: "email" });
      router.push(redirectTo);
    }
  }

  async function handleGoogleLogin() {
    setLoading(true);
    setError(null);

    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(redirectTo)}`,
      },
    });

    if (oauthError) {
      setError(oauthError.message);
      setLoading(false);
      trackAuthEvent("login_failure", {
        reason: sanitizeErrorForAnalytics(oauthError.message),
        method: "google",
      });
    } else {
      trackAuthEvent("login_attempt", { method: "google" });
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-950">
      <div className="w-full max-w-sm space-y-6 px-4">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-white">Attic</h1>
          <p className="mt-2 text-sm text-neutral-400">
            Your TikTok history, organized and searchable.
          </p>
        </div>

        {/* Status messages */}
        {messageParam === "account_deleted" && (
          <p className="text-center text-sm text-green-400">
            Your account has been deleted.
          </p>
        )}
        {info && (
          <p className="text-center text-sm text-blue-400">{info}</p>
        )}

        {/* Google OAuth */}
        <button
          onClick={handleGoogleLogin}
          disabled={loading}
          className="flex w-full items-center justify-center gap-3 rounded-lg bg-white px-4 py-3 text-sm font-medium text-neutral-900 transition-colors hover:bg-neutral-100 disabled:opacity-50"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24">
            <path
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
              fill="#4285F4"
            />
            <path
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              fill="#34A853"
            />
            <path
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              fill="#FBBC05"
            />
            <path
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              fill="#EA4335"
            />
          </svg>
          Continue with Google
        </button>

        <div className="flex items-center gap-3">
          <div className="h-px flex-1 bg-neutral-800" />
          <span className="text-xs text-neutral-500">or</span>
          <div className="h-px flex-1 bg-neutral-800" />
        </div>

        {/* Email/Password form */}
        <form onSubmit={handleEmailAuth} className="space-y-4">
          <div>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              required
              disabled={loading}
              className="w-full rounded-lg border border-neutral-700 bg-neutral-900 px-4 py-3 text-sm text-white placeholder-neutral-500 focus:border-blue-500 focus:outline-none disabled:opacity-50"
            />
          </div>

          {mode !== "forgot" && (
            <div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                required
                minLength={6}
                disabled={loading}
                className="w-full rounded-lg border border-neutral-700 bg-neutral-900 px-4 py-3 text-sm text-white placeholder-neutral-500 focus:border-blue-500 focus:outline-none disabled:opacity-50"
              />
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-blue-600 px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-blue-500 disabled:opacity-50"
          >
            {loading
              ? "..."
              : mode === "signin"
                ? "Sign in"
                : mode === "signup"
                  ? "Create account"
                  : "Send reset link"}
          </button>
        </form>

        {/* Mode toggles */}
        <div className="flex flex-col items-center gap-2 text-sm">
          {mode === "signin" && (
            <>
              <button
                onClick={() => {
                  setMode("forgot");
                  setError(null);
                }}
                className="text-neutral-400 hover:text-white"
              >
                Forgot password?
              </button>
              <button
                onClick={() => {
                  setMode("signup");
                  setError(null);
                }}
                className="text-neutral-400 hover:text-white"
              >
                Don&apos;t have an account?{" "}
                <span className="text-blue-400">Sign up</span>
              </button>
            </>
          )}
          {mode === "signup" && (
            <button
              onClick={() => {
                setMode("signin");
                setError(null);
              }}
              className="text-neutral-400 hover:text-white"
            >
              Already have an account?{" "}
              <span className="text-blue-400">Sign in</span>
            </button>
          )}
          {mode === "forgot" && (
            <button
              onClick={() => {
                setMode("signin");
                setError(null);
                setInfo(null);
              }}
              className="text-neutral-400 hover:text-white"
            >
              Back to sign in
            </button>
          )}
        </div>

        {/* Dev quick login */}
        {isDev && mode === "signin" && (
          <div className="rounded-lg border border-amber-800/50 bg-amber-950/30 p-3">
            <p className="mb-2 text-xs text-amber-300">
              Dev mode — credentials pre-filled
            </p>
            <p className="text-xs text-amber-400/70">
              test@attic.dev / testtest123
            </p>
          </div>
        )}

        {error && (
          <p className="text-center text-sm text-red-400">{error}</p>
        )}
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
