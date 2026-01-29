/**
 * Supabase client utilities index.
 *
 * Re-exports all Supabase utilities for convenient importing.
 */

// Browser client
export { createClient as createBrowserClient } from "./client"

// Server client and helpers
export { createClient as createServerClient, getUser, getSession } from "./server"

// Types
export type { AuthState, UseUserReturn } from "./types"
