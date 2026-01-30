"use client";

/**
 * Consent modal component for data processing disclosure.
 *
 * Displays what data Attic accesses and how it's used before
 * allowing processing to begin. Consent must be explicitly
 * captured and recorded with version tracking.
 */

import * as React from "react";
import { Check, X, Lock, Calendar, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { CONSENT_CONTENT, type ConsentSection } from "@/lib/consent/content";

/**
 * Props for the ConsentModal component.
 */
export interface ConsentModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Upload ID to record consent for */
  uploadId: string;
  /** Called when user cancels (closes modal without consenting) */
  onCancel: () => void;
  /** Called when user consents (after successful API call) */
  onConsent: () => void;
  /** Optional loading state while recording consent */
  isLoading?: boolean;
  /** Optional error message to display */
  error?: string | null;
  /** Custom class name for the dialog content */
  className?: string;
}

/**
 * Icon component mapping for consent sections.
 */
function SectionIcon({
  icon,
  className,
}: {
  icon: string;
  className?: string;
}) {
  const iconClass = cn("h-5 w-5", className);

  switch (icon) {
    case "check":
      return <Check className={cn(iconClass, "text-green-600")} />;
    case "x":
      return <X className={cn(iconClass, "text-red-500")} />;
    case "lock":
      return <Lock className={cn(iconClass, "text-blue-600")} />;
    case "calendar":
      return <Calendar className={cn(iconClass, "text-amber-600")} />;
    default:
      return null;
  }
}

/**
 * Renders a single consent section with icon, title, and items.
 */
function ConsentSectionBlock({
  section,
  className,
}: {
  section: ConsentSection;
  className?: string;
}) {
  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center gap-2">
        <SectionIcon icon={section.icon} />
        <h4 className="font-medium text-sm">{section.title}</h4>
      </div>
      <ul className="space-y-1 ml-7">
        {section.items.map((item, index) => (
          <li
            key={index}
            className="text-sm text-muted-foreground list-disc list-inside"
          >
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Consent modal component.
 *
 * Displays data usage disclosures and captures explicit user consent
 * before allowing data processing to begin.
 *
 * Features:
 * - Clear disclosure of what data is extracted
 * - Clear disclosure of what data is ignored
 * - Third-party data sharing disclosure (Apify, OpenAI)
 * - Data retention policy
 * - Cancel and Confirm buttons
 * - Loading state while recording consent
 * - Error state display
 *
 * @example
 * ```tsx
 * <ConsentModal
 *   isOpen={showConsent}
 *   uploadId="123e4567-e89b-12d3-a456-426614174000"
 *   onCancel={() => setShowConsent(false)}
 *   onConsent={() => handleConsentGiven()}
 *   isLoading={isRecordingConsent}
 * />
 * ```
 */
export function ConsentModal({
  isOpen,
  uploadId,
  onCancel,
  onConsent,
  isLoading = false,
  error = null,
  className,
}: ConsentModalProps) {
  // Track when the modal was opened for analytics
  const openedAtRef = React.useRef<number | null>(null);

  React.useEffect(() => {
    if (isOpen && !openedAtRef.current) {
      openedAtRef.current = Date.now();
    } else if (!isOpen) {
      openedAtRef.current = null;
    }
  }, [isOpen]);

  const handleConfirm = () => {
    onConsent();
  };

  const handleCancel = () => {
    onCancel();
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleCancel()}>
      <DialogContent
        className={cn("sm:max-w-lg max-h-[90vh] overflow-y-auto", className)}
        aria-describedby="consent-description"
      >
        <DialogHeader>
          <DialogTitle className="text-xl">
            {CONSENT_CONTENT.title}
          </DialogTitle>
          <DialogDescription id="consent-description" className="text-base">
            {CONSENT_CONTENT.intro}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          <ConsentSectionBlock section={CONSENT_CONTENT.whatWeExtract} />
          <ConsentSectionBlock section={CONSENT_CONTENT.whatWeIgnore} />
          <ConsentSectionBlock section={CONSENT_CONTENT.howWeProcess} />
          <ConsentSectionBlock section={CONSENT_CONTENT.dataRetention} />
        </div>

        {error && (
          <div
            className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive"
            role="alert"
          >
            {error}
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            type="button"
            variant="outline"
            onClick={handleCancel}
            disabled={isLoading}
          >
            {CONSENT_CONTENT.cancelLabel}
          </Button>
          <Button
            type="button"
            onClick={handleConfirm}
            disabled={isLoading}
            className="min-w-[160px]"
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Processing...
              </>
            ) : (
              CONSENT_CONTENT.confirmLabel
            )}
          </Button>
        </DialogFooter>

        {/* Hidden field for accessibility - screen readers can find the upload ID */}
        <span className="sr-only" data-upload-id={uploadId}>
          Recording consent for upload {uploadId}
        </span>
      </DialogContent>
    </Dialog>
  );
}

export default ConsentModal;
