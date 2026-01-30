import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";

// Prevent static prerendering - this page needs runtime auth check
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Processing - Attic",
  description: "Your TikTok data is being processed",
};

interface ProcessingPageProps {
  params: Promise<{
    id: string;
  }>;
}

/**
 * Processing page - Server Component.
 *
 * Shows processing progress for an upload.
 * This is a placeholder that will be fully implemented in Task 4.3.
 *
 * Protected route that requires authentication.
 */
export default async function ProcessingPage({ params }: ProcessingPageProps) {
  // Check for authenticated user
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // If not authenticated, redirect to login
  if (!user) {
    redirect("/auth/login");
  }

  const { id } = await params;

  return (
    <main className="min-h-screen bg-background flex flex-col items-center justify-center px-4">
      <div className="max-w-md w-full text-center space-y-6">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">
            Processing Your Data
          </h1>
          <p className="text-muted-foreground">
            Your TikTok export is being analyzed. This may take a few minutes.
          </p>
        </div>

        <div className="rounded-lg border bg-card p-6 space-y-4">
          <div className="flex items-center justify-center">
            <div className="h-12 w-12 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">Upload ID</p>
            <p className="text-xs text-muted-foreground font-mono break-all">
              {id}
            </p>
          </div>

          <p className="text-sm text-muted-foreground">
            You can leave this page and we&apos;ll email you when processing is
            complete.
          </p>
        </div>

        <p className="text-xs text-muted-foreground">
          Full processing status UI coming in Task 4.3
        </p>
      </div>
    </main>
  );
}
