"use client";

import { AppHeader } from "@/components/app-header";
import { useAuth } from "@/lib/auth-context";
import { trackAuthEvent } from "@/lib/posthog";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function SettingsPage() {
  const { user, loading, supabase } = useAuth();
  const router = useRouter();
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Redirect to login if session expires or is missing
  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="flex h-screen flex-col bg-neutral-950">
        <AppHeader />
        <div className="flex flex-1 items-center justify-center">
          <span className="text-neutral-400">Loading...</span>
        </div>
      </div>
    );
  }

  async function handleSignOut() {
    trackAuthEvent("logout");
    await supabase.auth.signOut();
    router.push("/login");
  }

  async function handleDeleteAccount() {
    if (deleteConfirm !== "DELETE") return;

    setDeleting(true);
    setError(null);

    try {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      if (!token) {
        setError("Not authenticated.");
        setDeleting(false);
        return;
      }

      const response = await fetch(`${API_URL}/api/user/me`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) {
        const body = await response.json().catch(() => null);
        setError(body?.detail?.detail ?? "Account deletion failed.");
        setDeleting(false);
        return;
      }

      trackAuthEvent("account_deleted");
      await supabase.auth.signOut();
      router.push("/login?message=account_deleted");
    } catch {
      setError("Could not reach the server. Please try again.");
      setDeleting(false);
    }
  }

  return (
    <div className="flex h-screen flex-col bg-neutral-950">
      <AppHeader />

      <div className="flex-1 overflow-y-auto px-4 py-8">
        <div className="mx-auto max-w-lg space-y-8">
          <h1 className="text-2xl font-bold text-white">Settings</h1>

          {/* Account info */}
          <section className="space-y-4 rounded-lg border border-neutral-800 p-6">
            <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-400">
              Account
            </h2>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-neutral-500">Email</label>
                <p className="text-sm text-white">{user?.email ?? "—"}</p>
              </div>
              <div>
                <label className="text-xs text-neutral-500">
                  Auth provider
                </label>
                <p className="text-sm text-white">
                  {user?.app_metadata?.provider ?? "email"}
                </p>
              </div>
            </div>
          </section>

          {/* Sign out */}
          <section className="space-y-4 rounded-lg border border-neutral-800 p-6">
            <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-400">
              Session
            </h2>
            <button
              onClick={handleSignOut}
              className="rounded-lg border border-neutral-700 px-4 py-2 text-sm text-neutral-300 transition-colors hover:bg-neutral-800 hover:text-white"
            >
              Sign out
            </button>
          </section>

          {/* Danger zone */}
          <section className="space-y-4 rounded-lg border border-red-900/50 p-6">
            <h2 className="text-sm font-medium uppercase tracking-wider text-red-400">
              Danger zone
            </h2>
            <p className="text-sm text-neutral-400">
              Permanently delete your account and all associated data. This
              action cannot be undone.
            </p>

            {!showDeleteDialog ? (
              <button
                onClick={() => setShowDeleteDialog(true)}
                className="rounded-lg border border-red-800 px-4 py-2 text-sm text-red-400 transition-colors hover:bg-red-950 hover:text-red-300"
              >
                Delete my account
              </button>
            ) : (
              <div className="space-y-3 rounded-lg border border-red-800/50 bg-red-950/20 p-4">
                <p className="text-sm text-red-300">
                  Type <span className="font-mono font-bold">DELETE</span> to
                  confirm.
                </p>
                <input
                  type="text"
                  value={deleteConfirm}
                  onChange={(e) => setDeleteConfirm(e.target.value)}
                  placeholder="Type DELETE"
                  disabled={deleting}
                  className="w-full rounded-lg border border-red-800 bg-neutral-900 px-4 py-2 text-sm text-white placeholder-neutral-500 focus:border-red-500 focus:outline-none disabled:opacity-50"
                />
                <div className="flex gap-2">
                  <button
                    onClick={handleDeleteAccount}
                    disabled={deleteConfirm !== "DELETE" || deleting}
                    className="rounded-lg bg-red-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-600 disabled:opacity-50"
                  >
                    {deleting ? "Deleting..." : "Permanently delete"}
                  </button>
                  <button
                    onClick={() => {
                      setShowDeleteDialog(false);
                      setDeleteConfirm("");
                      setError(null);
                    }}
                    disabled={deleting}
                    className="rounded-lg border border-neutral-700 px-4 py-2 text-sm text-neutral-300 transition-colors hover:bg-neutral-800 disabled:opacity-50"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {error && <p className="text-sm text-red-400">{error}</p>}
          </section>
        </div>
      </div>
    </div>
  );
}
