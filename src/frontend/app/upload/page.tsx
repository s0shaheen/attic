import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";
import { UploadPageContent } from "./UploadPageContent";

// Prevent static prerendering - this page needs runtime auth check
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Upload - Attic",
  description: "Upload your TikTok data export to get started with Attic",
};

/**
 * Upload page - Server Component.
 *
 * Protected route that requires authentication.
 * Redirects to login if user is not authenticated.
 */
export default async function UploadPage() {
  // Check for authenticated user
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // If not authenticated, redirect to login
  if (!user) {
    redirect("/auth/login?returnTo=/upload");
  }

  // TODO: Fetch user's tier limit from profile/subscription
  // For now, use free tier default
  const tierLimit = 200;

  return <UploadPageContent tierLimit={tierLimit} />;
}
