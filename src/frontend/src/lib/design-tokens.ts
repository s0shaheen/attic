/**
 * Attic Design Tokens — Single source of truth for the Parchment + Ink design system.
 *
 * Reference: docs/BRAND.md
 * Usage: CSS custom properties consume these values via globals.css
 */

export const tokens = {
  colors: {
    parchment: "#F8F7F4",
    white: "#FFFFFF",
    ink: "#1C1B18",
    softBlack: "#2C2926",
    stone: "#9C9890",
    border: "#E6E4DE",
    borderHover: "#D0CCC4",
    subtle: "#F0EEE8",
    cinnamon: {
      default: "#A06840",
      light: "#BC8058",
      dark: "#7E5030",
      subtle: "rgba(160, 104, 64, 0.07)",
      border: "rgba(160, 104, 64, 0.15)",
    },
    semantic: {
      error: { color: "#B54040", bg: "#FDF2F2", border: "#E8BCBC", text: "#8C2D2D" },
      success: { color: "#3D7A4A", bg: "#F2F8F3", border: "#BCE8C4", text: "#2E5E38" },
      warning: { color: "#A07830", bg: "#FDF8F0", border: "#E8D8B8", text: "#7A5C24" },
      info: { color: "#4A6A8A", bg: "#F0F4F8", border: "#B8CCE0", text: "#3A5470" },
    },
  },
  typography: {
    fonts: {
      display: "var(--font-display)", // Crimson Pro
      sans: "var(--font-sans)", // DM Sans
      mono: "var(--font-mono)", // DM Mono
    },
    scale: {
      xs: "12px",
      sm: "13px",
      base: "14px",
      md: "15px",
      lg: "17px",
      xl: "20px",
      "2xl": "24px",
      "3xl": "30px",
      "4xl": "48px",
    },
  },
  spacing: {
    radius: {
      sm: "6px",
      md: "8px",
      lg: "12px",
      full: "9999px",
    },
  },
} as const;
