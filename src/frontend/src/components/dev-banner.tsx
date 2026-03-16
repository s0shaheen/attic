"use client";

import { useAuth } from "@/lib/auth-context";

const isDev = process.env.NEXT_PUBLIC_ENVIRONMENT === "development";

export function DevBanner() {
  const { user } = useAuth();

  if (!isDev) return null;

  return (
    <div className="flex items-center justify-center gap-2 bg-amber-900/40 px-4 py-1 text-xs text-amber-300">
      <span className="font-medium">Dev mode</span>
      {user?.email && (
        <>
          <span className="text-amber-500">&middot;</span>
          <span>{user.email}</span>
        </>
      )}
    </div>
  );
}
