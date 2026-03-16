"use client";

import Link from "next/link";

export default function VerifyPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-950">
      <div className="w-full max-w-sm space-y-6 px-4 text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-blue-600/20">
          <svg
            className="h-8 w-8 text-blue-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
            />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-white">Check your email</h1>
        <p className="text-sm text-neutral-400">
          We sent you a confirmation link. Click it to verify your account and
          start using Attic.
        </p>
        <Link
          href="/login"
          className="inline-block text-sm text-blue-400 hover:text-blue-300"
        >
          Back to sign in
        </Link>
      </div>
    </div>
  );
}
