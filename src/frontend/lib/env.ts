/**
 * Validated environment variables for the frontend.
 *
 * This module uses Zod to validate environment variables at build time,
 * ensuring all required values are present and correctly formatted.
 * Missing or invalid values will cause the build to fail with clear errors.
 */

import { z } from "zod"

const envSchema = z.object({
  // Supabase
  NEXT_PUBLIC_SUPABASE_URL: z
    .string()
    .url("NEXT_PUBLIC_SUPABASE_URL must be a valid URL"),
  NEXT_PUBLIC_SUPABASE_ANON_KEY: z
    .string()
    .min(1, "NEXT_PUBLIC_SUPABASE_ANON_KEY is required"),

  // API
  NEXT_PUBLIC_API_URL: z
    .string()
    .url("NEXT_PUBLIC_API_URL must be a valid URL"),

  // Observability (optional)
  NEXT_PUBLIC_POSTHOG_KEY: z.string().optional(),
  NEXT_PUBLIC_SENTRY_DSN: z.string().optional(),

  // Application
  NEXT_PUBLIC_ENVIRONMENT: z
    .enum(["development", "staging", "production"])
    .default("development"),
})

/**
 * Parse and validate environment variables.
 * Throws a detailed error if validation fails.
 */
function getEnv() {
  const parsed = envSchema.safeParse({
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_POSTHOG_KEY: process.env.NEXT_PUBLIC_POSTHOG_KEY,
    NEXT_PUBLIC_SENTRY_DSN: process.env.NEXT_PUBLIC_SENTRY_DSN,
    NEXT_PUBLIC_ENVIRONMENT: process.env.NEXT_PUBLIC_ENVIRONMENT,
  })

  if (!parsed.success) {
    console.error(
      "❌ Invalid environment variables:",
      parsed.error.flatten().fieldErrors
    )
    throw new Error("Invalid environment variables")
  }

  return parsed.data
}

/**
 * Validated environment variables.
 * Access these instead of process.env directly for type safety.
 */
export const env = getEnv()

/**
 * Type for the validated environment.
 */
export type Env = z.infer<typeof envSchema>
