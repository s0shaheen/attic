/**
 * Consent screen content and version management.
 *
 * This module defines the consent text shown to users before processing begins.
 * The content matches PRD F3 requirements exactly.
 *
 * IMPORTANT: When updating consent text, increment CONSENT_VERSION.
 * Users with older consent versions will need to re-consent.
 */

/**
 * Current version of the consent text.
 * Increment when consent content changes.
 */
export const CONSENT_VERSION = "1.0.0";

/**
 * Structure for a consent section with icon, title, and items.
 */
export interface ConsentSection {
  /** Icon to display (emoji or icon name) */
  icon: string;
  /** Section title */
  title: string;
  /** List of items/disclosures in this section */
  items: string[];
}

/**
 * Full consent content structure.
 */
export interface ConsentContent {
  version: string;
  title: string;
  intro: string;
  whatWeExtract: ConsentSection;
  whatWeIgnore: ConsentSection;
  howWeProcess: ConsentSection;
  dataRetention: ConsentSection;
  cancelLabel: string;
  confirmLabel: string;
}

/**
 * Consent screen content matching PRD F3 requirements.
 *
 * This content must be shown to users before processing their TikTok data.
 * Any changes to this content require incrementing CONSENT_VERSION.
 */
export const CONSENT_CONTENT: ConsentContent = {
  version: CONSENT_VERSION,
  title: "Before we continue...",
  intro: "Attic will analyze your TikTok data. Here's exactly what we access:",

  whatWeExtract: {
    icon: "check",
    title: "What we extract",
    items: [
      "Liked video URLs and timestamps",
      "Favorited video URLs and timestamps",
    ],
  },

  whatWeIgnore: {
    icon: "x",
    title: "What we ignore (never accessed)",
    items: [
      "Direct messages",
      "Search history",
      "Comments you posted",
      "Your profile information",
      "Watch history",
    ],
  },

  howWeProcess: {
    icon: "lock",
    title: "How we process",
    items: [
      "Video URLs are sent to our enrichment service (Apify) to fetch public metadata",
      "Video thumbnails are sent to OpenAI for visual analysis",
      "No personal identifiers are sent to third parties",
    ],
  },

  dataRetention: {
    icon: "calendar",
    title: "Data retention",
    items: [
      "Your data is stored until you delete it or 30 days after your subscription ends",
    ],
  },

  cancelLabel: "Cancel",
  confirmLabel: "I Understand, Continue",
};

/**
 * Get the current consent version.
 */
export function getCurrentConsentVersion(): string {
  return CONSENT_VERSION;
}

/**
 * Check if a consent version is current.
 */
export function isConsentVersionCurrent(version: string): boolean {
  return version === CONSENT_VERSION;
}
