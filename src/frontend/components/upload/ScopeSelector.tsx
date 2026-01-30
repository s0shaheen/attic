"use client";

/**
 * Scope selector component for choosing which videos to process.
 *
 * Allows users to select between liked videos only, favorited videos only,
 * or both. Shows counts for each option and indicates if selection
 * exceeds tier limit.
 */

import * as React from "react";
import { Heart, Star, Sparkles, AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { Scope } from "@/lib/api/uploads";

/**
 * Props for the ScopeSelector component.
 */
export interface ScopeSelectorProps {
  /** Number of liked videos available */
  likedCount: number;
  /** Number of favorited videos available */
  favoritedCount: number;
  /** Currently selected scope */
  selectedScope: Scope | null;
  /** Called when a scope is selected */
  onSelect: (scope: Scope) => void;
  /** Called when user confirms selection */
  onConfirm: () => void;
  /** User's tier limit */
  tierLimit: number;
  /** Whether the component is in loading state */
  isLoading?: boolean;
  /** Disable if over limit */
  overLimit?: boolean;
  /** Custom class name */
  className?: string;
}

/**
 * Scope option card data.
 */
interface ScopeOption {
  value: Scope;
  label: string;
  description: string;
  icon: React.ReactNode;
  getCount: (liked: number, favorited: number) => number;
}

const SCOPE_OPTIONS: ScopeOption[] = [
  {
    value: "liked",
    label: "Liked Videos",
    description: "Videos you've liked on TikTok",
    icon: <Heart className="h-5 w-5" />,
    getCount: (liked) => liked,
  },
  {
    value: "favorited",
    label: "Favorited Videos",
    description: "Videos you've saved to favorites",
    icon: <Star className="h-5 w-5" />,
    getCount: (_, favorited) => favorited,
  },
  {
    value: "both",
    label: "Both",
    description: "Liked and favorited videos",
    icon: <Sparkles className="h-5 w-5" />,
    getCount: (liked) => liked, // Use liked count as primary
  },
];

/**
 * Scope selector component.
 *
 * Features:
 * - Visual cards for each scope option
 * - Shows counts for each option
 * - Highlights selected option
 * - Shows warning if over tier limit
 * - Confirm button to proceed
 *
 * @example
 * ```tsx
 * <ScopeSelector
 *   likedCount={500}
 *   favoritedCount={150}
 *   selectedScope={scope}
 *   onSelect={setScope}
 *   onConfirm={handleConfirm}
 *   tierLimit={200}
 * />
 * ```
 */
export function ScopeSelector({
  likedCount,
  favoritedCount,
  selectedScope,
  onSelect,
  onConfirm,
  tierLimit,
  isLoading = false,
  className,
}: ScopeSelectorProps) {
  const getCount = (option: ScopeOption) =>
    option.getCount(likedCount, favoritedCount);

  const isOverLimit = (option: ScopeOption) =>
    getCount(option) > tierLimit;

  const selectedCount = selectedScope
    ? SCOPE_OPTIONS.find((o) => o.value === selectedScope)?.getCount(
        likedCount,
        favoritedCount
      ) ?? 0
    : 0;

  const selectedOverLimit = selectedCount > tierLimit;

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader>
        <CardTitle>What would you like to analyze?</CardTitle>
        <CardDescription>
          Choose which videos to include in your library. Your{" "}
          {tierLimit.toLocaleString()} video limit applies.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Scope options */}
        <div className="grid gap-3 sm:grid-cols-3">
          {SCOPE_OPTIONS.map((option) => {
            const count = getCount(option);
            const overLimit = isOverLimit(option);
            const isSelected = selectedScope === option.value;

            return (
              <button
                key={option.value}
                onClick={() => onSelect(option.value)}
                disabled={isLoading || count === 0}
                className={cn(
                  "relative flex flex-col items-center gap-2 rounded-lg border-2 p-4 text-center transition-all",
                  "hover:border-primary/50 hover:bg-accent/50",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                  "disabled:cursor-not-allowed disabled:opacity-50",
                  isSelected
                    ? "border-primary bg-primary/5"
                    : "border-border bg-card",
                  overLimit && !isSelected && "border-amber-300 bg-amber-50/50"
                )}
                aria-pressed={isSelected}
              >
                <div
                  className={cn(
                    "flex h-10 w-10 items-center justify-center rounded-full",
                    isSelected
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  {option.icon}
                </div>

                <div>
                  <p className="font-medium">{option.label}</p>
                  <p className="text-sm text-muted-foreground">
                    {option.description}
                  </p>
                </div>

                <p
                  className={cn(
                    "text-2xl font-bold",
                    count === 0 && "text-muted-foreground"
                  )}
                >
                  {count.toLocaleString()}
                </p>

                {overLimit && (
                  <div className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-amber-500 text-white">
                    <AlertTriangle className="h-3 w-3" />
                  </div>
                )}
              </button>
            );
          })}
        </div>

        {/* Over limit warning */}
        {selectedOverLimit && (
          <div className="flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 p-4 dark:bg-amber-950/20">
            <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600" />
            <div>
              <p className="font-medium text-amber-800 dark:text-amber-200">
                Over your limit
              </p>
              <p className="text-sm text-amber-700 dark:text-amber-300">
                You selected {selectedCount.toLocaleString()} videos, but your
                plan allows {tierLimit.toLocaleString()}. Only the first{" "}
                {tierLimit.toLocaleString()} videos will be processed.
                <button className="ml-1 text-primary underline hover:no-underline">
                  Upgrade for more
                </button>
              </p>
            </div>
          </div>
        )}

        {/* No videos warning */}
        {likedCount === 0 && favoritedCount === 0 && (
          <div className="rounded-lg border border-muted bg-muted/50 p-4 text-center">
            <p className="text-sm text-muted-foreground">
              No videos found in your export. Make sure you have liked or
              favorited videos on TikTok.
            </p>
          </div>
        )}

        {/* Confirm button */}
        <div className="flex justify-end pt-2">
          <Button
            onClick={onConfirm}
            disabled={!selectedScope || isLoading || selectedCount === 0}
            size="lg"
          >
            Continue
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default ScopeSelector;
