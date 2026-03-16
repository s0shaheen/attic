"use client";

/**
 * Auth context provider for Supabase session management.
 *
 * Data flow:
 *   AuthProvider (fetches session once, listens to onAuthStateChange)
 *       └── useAuth() → { user, loading, supabase }
 *            ├── AppHeader (user menu, sign out)
 *            ├── Settings page (user info, delete account)
 *            ├── Chat page (access token for API calls)
 *            └── Upload page (access token for API calls)
 */

import { createClient } from "@/lib/supabase/client";
import type { SupabaseClient, User } from "@supabase/supabase-js";
import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

interface AuthState {
  user: User | null;
  loading: boolean;
  supabase: SupabaseClient;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  // Create the Supabase client once inside the React lifecycle (not at
  // module scope) so it is never accidentally imported server-side where
  // browser cookie storage is unavailable.
  const supabaseRef = useRef<SupabaseClient>(null);
  if (supabaseRef.current === null) {
    supabaseRef.current = createClient();
  }
  const supabase = supabaseRef.current;

  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session?.user ?? null);
      setLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, [supabase]);

  return (
    <AuthContext.Provider value={{ user, loading, supabase }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
