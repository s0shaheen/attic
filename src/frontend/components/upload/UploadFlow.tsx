"use client";

/**
 * Upload flow orchestration component.
 *
 * Manages the complete upload flow:
 * 1. Export guide / instructions
 * 2. File upload
 * 3. Validation
 * 4. Scope selection
 * 5. Consent capture
 * 6. Redirect to processing
 */

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { useUploadFlow } from "@/hooks/useUploadFlow";
import { ExportGuide } from "./ExportGuide";
import { SimpleFileUploader, type UploadResult } from "./SimpleFileUploader";
import { ScopeSelector } from "./ScopeSelector";
import { UploadSummary } from "./UploadSummary";
import { ValidationError } from "./ValidationError";
import { ConsentModal } from "./ConsentModal";
import { recordConsent } from "@/lib/api/uploads";
import { createClient } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";

/**
 * Props for the UploadFlow component.
 */
export interface UploadFlowProps {
  /** User's tier limit */
  tierLimit?: number;
  /** Custom class name */
  className?: string;
}

/**
 * Estimate processing time based on item count.
 * Rough estimate: 2 seconds per item.
 */
function estimateProcessingMinutes(itemCount: number): number {
  return Math.ceil((itemCount * 2) / 60);
}

/**
 * Upload flow component.
 *
 * Orchestrates the entire upload experience from instructions
 * through to consent and redirect to processing.
 *
 * Features:
 * - Step-by-step flow
 * - Cannot skip steps
 * - Clear error handling
 * - Mobile responsive
 *
 * @example
 * ```tsx
 * <UploadFlow tierLimit={200} />
 * ```
 */
export function UploadFlow({ tierLimit = 200, className }: UploadFlowProps) {
  const router = useRouter();
  const { state, actions } = useUploadFlow();

  const [guideExpanded, setGuideExpanded] = React.useState(true);
  const [consentError, setConsentError] = React.useState<string | null>(null);
  const [isRecordingConsent, setIsRecordingConsent] = React.useState(false);

  // Initialize tier limit
  React.useEffect(() => {
    actions.setTierLimit(tierLimit);
  }, [tierLimit, actions]);

  /**
   * Handle upload completion.
   */
  const handleUploadComplete = React.useCallback(
    (result: UploadResult) => {
      actions.onUploadComplete(result);
      // Collapse guide once upload is done
      setGuideExpanded(false);

      // Simulate validation (in real implementation, this would call the API)
      // The validation would be triggered by the backend after upload
      setTimeout(() => {
        actions.onValidationComplete({
          valid: true,
          errorCode: null,
          errorMessage: null,
          likedCount: 450,
          favoritedCount: 120,
          fileHash: "mock-hash",
        });
      }, 1500);
    },
    [actions]
  );

  /**
   * Handle upload error.
   */
  const handleUploadError = React.useCallback(
    (error: Error) => {
      actions.onUploadError(error);
    },
    [actions]
  );

  /**
   * Handle scope confirmation.
   */
  const handleScopeConfirm = React.useCallback(() => {
    const itemCount = Math.min(state.totalItems, state.tierLimit);
    actions.setEstimatedMinutes(estimateProcessingMinutes(itemCount));
    actions.confirmScope();
  }, [actions, state.totalItems, state.tierLimit]);

  /**
   * Handle consent given.
   */
  const handleConsent = React.useCallback(async () => {
    if (!state.uploadId) return;

    setIsRecordingConsent(true);
    setConsentError(null);

    try {
      // Get auth token
      const supabase = createClient();
      if (!supabase) {
        throw new Error("Unable to connect to authentication service");
      }

      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error("Please sign in to continue");
      }

      // Record consent
      await recordConsent(state.uploadId, session.access_token);

      // Move to complete state and redirect
      actions.giveConsent();

      // Redirect to processing page
      router.push(`/processing/${state.uploadId}`);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to record consent";
      setConsentError(message);
    } finally {
      setIsRecordingConsent(false);
    }
  }, [state.uploadId, actions, router]);

  /**
   * Handle consent cancel.
   */
  const handleConsentCancel = React.useCallback(() => {
    actions.cancelConsent();
    setConsentError(null);
  }, [actions]);

  /**
   * Handle retry from error state.
   */
  const handleRetry = React.useCallback(() => {
    actions.retry();
    setGuideExpanded(true);
  }, [actions]);

  return (
    <div className={cn("w-full max-w-2xl mx-auto space-y-6", className)}>
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold tracking-tight">
          Upload Your TikTok Data
        </h1>
        <p className="mt-2 text-muted-foreground">
          Get personalized insights from your TikTok activity
        </p>
      </div>

      {/* Export Guide - Always visible (collapsible) */}
      <ExportGuide
        isExpanded={guideExpanded}
        onToggle={() => setGuideExpanded(!guideExpanded)}
      />

      {/* Instructions / Upload Step */}
      {(state.step === "instructions" || state.step === "uploading") && (
        <div className="space-y-4">
          <SimpleFileUploader
            onUploadComplete={handleUploadComplete}
            onUploadError={handleUploadError}
            onUploadCancel={actions.onUploadCancel}
            onUploadStart={actions.startUpload}
          />

          {/* Upload error */}
          {state.error && state.step === "instructions" && (
            <ValidationError
              errorCode={state.error.code}
              errorMessage={state.error.message}
              onRetry={handleRetry}
              onDismiss={handleRetry}
            />
          )}
        </div>
      )}

      {/* Validating Step */}
      {state.step === "validating" && (
        <div className="flex flex-col items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="mt-4 text-lg font-medium">Validating your export...</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Checking file contents and counting your videos
          </p>
        </div>
      )}

      {/* Invalid Step */}
      {state.step === "invalid" && state.error && (
        <ValidationError
          errorCode={state.error.code}
          errorMessage={state.error.message}
          onRetry={handleRetry}
        />
      )}

      {/* Scope Selection Step */}
      {state.step === "scope" && (
        <div className="space-y-4">
          <ScopeSelector
            likedCount={state.likedCount}
            favoritedCount={state.favoritedCount}
            selectedScope={state.selectedScope}
            onSelect={actions.selectScope}
            onConfirm={handleScopeConfirm}
            tierLimit={state.tierLimit}
            isLoading={state.isLoading}
          />

          {/* Summary when scope selected */}
          {state.selectedScope && (
            <UploadSummary
              totalItems={state.totalItems}
              tierLimit={state.tierLimit}
              estimatedMinutes={estimateProcessingMinutes(
                Math.min(state.totalItems, state.tierLimit)
              )}
              withinLimit={state.withinLimit}
            />
          )}
        </div>
      )}

      {/* Consent Modal */}
      <ConsentModal
        isOpen={state.step === "consent"}
        uploadId={state.uploadId || ""}
        onCancel={handleConsentCancel}
        onConsent={handleConsent}
        isLoading={isRecordingConsent}
        error={consentError}
      />

      {/* Complete / Redirecting Step */}
      {state.step === "complete" && (
        <div className="flex flex-col items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="mt-4 text-lg font-medium">Starting processing...</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Redirecting to your processing page
          </p>
        </div>
      )}

      {/* Progress indicator */}
      <div className="flex justify-center">
        <div className="flex items-center gap-2">
          {["upload", "scope", "consent"].map((step, index) => {
            const stepMap: Record<string, number> = {
              instructions: 0,
              uploading: 0,
              validating: 0,
              invalid: 0,
              scope: 1,
              consent: 2,
              complete: 3,
            };
            const currentStepIndex = stepMap[state.step] ?? 0;
            const isActive = index === currentStepIndex;
            const isComplete = index < currentStepIndex;

            return (
              <React.Fragment key={step}>
                {index > 0 && (
                  <div
                    className={cn(
                      "h-0.5 w-8",
                      isComplete ? "bg-primary" : "bg-muted"
                    )}
                  />
                )}
                <div
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium",
                    isComplete && "bg-primary text-primary-foreground",
                    isActive && "border-2 border-primary text-primary",
                    !isComplete && !isActive && "bg-muted text-muted-foreground"
                  )}
                >
                  {index + 1}
                </div>
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default UploadFlow;
