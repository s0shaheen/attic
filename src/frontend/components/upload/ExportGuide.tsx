"use client";

/**
 * TikTok export guide component.
 *
 * Displays step-by-step instructions for how to download
 * a TikTok data export. Collapsible to save space after
 * users have read it.
 */

import * as React from "react";
import { ChevronDown, ChevronUp, ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

/**
 * Props for the ExportGuide component.
 */
export interface ExportGuideProps {
  /** Whether the guide is expanded */
  isExpanded: boolean;
  /** Toggle expansion callback */
  onToggle: () => void;
  /** Custom class name */
  className?: string;
}

/**
 * Export guide steps.
 */
const EXPORT_STEPS = [
  {
    step: 1,
    instruction: "Open the TikTok app on your phone",
    detail: "Go to your Profile tab",
  },
  {
    step: 2,
    instruction: "Tap the menu icon",
    detail: "It's the three horizontal lines (hamburger icon) in the top right",
  },
  {
    step: 3,
    instruction: "Go to Settings and privacy",
    detail: null,
  },
  {
    step: 4,
    instruction: "Tap Account",
    detail: null,
  },
  {
    step: 5,
    instruction: 'Select "Download your data"',
    detail: null,
  },
  {
    step: 6,
    instruction: 'Choose "JSON" format',
    detail: "This is important - TXT format won't work",
  },
  {
    step: 7,
    instruction: "Request your data",
    detail: "TikTok will email you when it's ready (usually 1-3 days)",
  },
  {
    step: 8,
    instruction: "Download the ZIP file from TikTok",
    detail: "Then upload it here",
  },
];

/**
 * Displays step-by-step instructions for downloading TikTok data export.
 *
 * Features:
 * - Collapsible to save space
 * - Clear numbered steps
 * - Highlights critical format requirement (JSON)
 * - Link to TikTok settings
 *
 * @example
 * ```tsx
 * const [expanded, setExpanded] = useState(true);
 *
 * <ExportGuide
 *   isExpanded={expanded}
 *   onToggle={() => setExpanded(!expanded)}
 * />
 * ```
 */
export function ExportGuide({
  isExpanded,
  onToggle,
  className,
}: ExportGuideProps) {
  return (
    <Card className={cn("w-full", className)}>
      <CardHeader
        className="cursor-pointer select-none"
        onClick={onToggle}
        role="button"
        aria-expanded={isExpanded}
        aria-controls="export-guide-content"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onToggle();
          }
        }}
      >
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg">
              How to Download Your TikTok Data
            </CardTitle>
            <CardDescription>
              Step-by-step instructions to get your data export
            </CardDescription>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0"
            onClick={(e) => {
              e.stopPropagation();
              onToggle();
            }}
            aria-label={isExpanded ? "Collapse guide" : "Expand guide"}
          >
            {isExpanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </Button>
        </div>
      </CardHeader>

      <div
        id="export-guide-content"
        className={cn(
          "overflow-hidden transition-all duration-300",
          isExpanded ? "max-h-[1000px] opacity-100" : "max-h-0 opacity-0"
        )}
      >
        <CardContent className="pt-0">
          <ol className="space-y-4">
            {EXPORT_STEPS.map(({ step, instruction, detail }) => (
              <li key={step} className="flex gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-medium text-primary">
                  {step}
                </span>
                <div>
                  <p className="font-medium text-foreground">{instruction}</p>
                  {detail && (
                    <p className="text-sm text-muted-foreground">{detail}</p>
                  )}
                </div>
              </li>
            ))}
          </ol>

          <div className="mt-6 rounded-lg bg-amber-50 p-4 dark:bg-amber-950/20">
            <p className="text-sm text-amber-800 dark:text-amber-200">
              <strong>Important:</strong> Make sure to select &quot;JSON&quot;
              format when requesting your data. The TXT format won&apos;t work
              with Attic.
            </p>
          </div>

          <div className="mt-4">
            <a
              href="https://www.tiktok.com/setting/download-your-data"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
            >
              Open TikTok data settings
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </CardContent>
      </div>
    </Card>
  );
}

export default ExportGuide;
