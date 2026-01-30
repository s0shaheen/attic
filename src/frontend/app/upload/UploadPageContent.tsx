"use client";

/**
 * Upload page content - Client Component.
 *
 * Contains the interactive upload flow UI.
 */

import { UploadFlow } from "@/components/upload/UploadFlow";

interface UploadPageContentProps {
  tierLimit: number;
}

/**
 * Upload page content component.
 *
 * Renders the upload flow within the page layout.
 */
export function UploadPageContent({ tierLimit }: UploadPageContentProps) {
  return (
    <main className="min-h-screen bg-background py-8 px-4">
      <UploadFlow tierLimit={tierLimit} />
    </main>
  );
}
