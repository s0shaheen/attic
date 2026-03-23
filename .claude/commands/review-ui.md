---
description: Review frontend changes against BRAND.md design system. Checks color tokens, typography, component patterns.
argument-hint: "[--file path/to/component.tsx]"
---

## Reference

Before running checks, read `docs/BRAND.md` for the authoritative design system. All rules below are derived from that document.

## Step 1: Get the diff

```bash
# Frontend changes only
git diff -- 'src/frontend/**' | head -2000
```

If `--file` is provided, read that file instead of the diff.

## Step 2: Color compliance

Scan every color value in the diff. This includes: hex values (#xxx, #xxxxxx), rgb/rgba values, Tailwind color classes, CSS custom property assignments.

### Hardcoded colors
Any color value that is NOT a CSS custom property (var(--color-*)) or a Tailwind class mapped to a token:
→ **BLOCK**: "Hardcoded color `{value}` at {file}:{line}. Use a design token CSS variable."

Exception: `transparent`, `inherit`, `currentColor` are fine.

### Cinnamon usage
Cinnamon tokens: `--color-cinnamon`, `--color-cinnamon-light`, `--color-cinnamon-dark`, `--color-cinnamon-subtle`, `--color-cinnamon-border`, or the raw hex values `#A06840`, `#BC8058`, `#7E5030`, rgba(160, 104, 64, *).

**Cinnamon is ALLOWED in these contexts only:**
- Landing page hero section
- Primary CTA buttons on marketing pages
- Reveal/Wrapped stat numbers
- "New" and "Beta" badge backgrounds
- Onboarding progress indicators
- Focus ring outlines (`:focus-visible`)
- Link hover color in marketing contexts
- Email template headers

**Cinnamon is BANNED in:**
- Chat message bubbles (user or assistant) → **BLOCK**
- Entity cards (restaurant, book, movie, etc.) → **BLOCK**
- Navigation bar/header chrome → **BLOCK**
- Everyday chips and tags → **BLOCK**
- Collection thumbnails or grid views → **BLOCK**
- Settings page → **BLOCK**
- Upload flow → **BLOCK**
- Any component that appears in the daily product experience → **BLOCK**

To determine context: look at the file path and component name.
- `components/chat/` → daily product, no Cinnamon
- `components/ui/chip*`, `components/ui/tag*` → daily product, no Cinnamon
- `app/page.tsx` (landing) → marketing, Cinnamon OK for CTAs/hero
- `components/reveal/`, `components/wrapped/` → special occasion, Cinnamon OK

## Step 3: Typography compliance

### Font family
- Product UI must use DM Sans (`font-sans` class, `var(--font-sans)`). If a product UI element uses `font-display` (Crimson Pro) → **BLOCK**
- Crimson Pro (`font-display`) is ONLY for:
  - The "attic" wordmark (`.wordmark` class)
  - Landing page hero headline
  - Reveal page stat numbers and section headers
  - Marketing page headlines
  - NOT for in-product h1/h2/h3 — those use DM Sans

### Font weights
- DM Sans: ONLY 400 (regular) and 500 (medium). Any other weight → **BLOCK**
  - `font-normal` (400) ✓
  - `font-medium` (500) ✓
  - `font-semibold` (600) → **BLOCK** on DM Sans
  - `font-bold` (700) → **BLOCK** on DM Sans
- Crimson Pro: 400, 500, 600 allowed. 700 only for reveal stat numbers.

### Type scale
Check sizes match the defined scale (12, 13, 14, 15, 17, 20, 24, 30, 48 px). Arbitrary sizes like 16px or 22px → **WARN**: "Size not in type scale. Use nearest token."

### Text transform
- `uppercase` / `text-transform: uppercase` on anything other than single-word labels (e.g., "NEW") → **WARN**
- No ALL CAPS multi-word text

### Line height and letter spacing
- DM Sans body: line-height 1.5
- Display headlines: line-height 1.25
- Compact UI: line-height 1.35
- Crimson Pro wordmark: letter-spacing -0.03em
- Display headlines: -0.02em
- DM Sans headers: -0.01em
- DM Sans body: 0

## Step 4: Component patterns

### Chat messages
- User bubble: background should be Soft Black (`--color-soft-black`, #2C2926), text Parchment. Right-aligned.
- Assistant message: White card background, Ink text, Border stroke. Left-aligned.
- Links in chat: underline only, no color change. Underline matches Stone on hover.
- Any deviation from this pattern → **BLOCK**

### Entity cards
- Background: White
- Border: 1px solid `--color-border`
- Radius: 12px (`--radius-lg`)
- Thumbnail: 44px square, 8px radius
- Title: Ink, medium weight. Metadata: Stone.
- NO accent colors on entity cards. Entity images provide all color.
- Any Cinnamon or accent color on an entity card → **BLOCK**

### Chips and tags
- Background: Subtle (`--color-subtle`, #F0EEE8)
- Text: Stone (`--color-stone`, #9C9890)
- Border: ink at 7% opacity
- Shape: pill (border-radius: 9999px / `--radius-full`)
- Exception: Cinnamon chips ONLY for marketing badges

### Thumbnail grids
- 3 or 4 columns
- 3px gap
- 6px border radius on outer corners only
- No borders on individual thumbnails
- Let images touch — the grid IS the visual

### Surfaces and depth
- Use 0.5px borders (Border color #E6E4DE), NOT box shadows
- Box shadows ONLY on: modals, popovers (shadow-lg)
- Focus rings use Cinnamon (this is an allowed Cinnamon context)
- If any box-shadow is added to a non-modal element → **WARN**: "Use border, not shadow per BRAND.md"

## Step 5: Token usage

If `src/frontend/src/lib/design-tokens.ts` exists, verify:
- Every new color value in the diff corresponds to a token
- If a value doesn't exist in tokens → **WARN**: "Add to design-tokens.ts first, then reference via CSS variable"
- Direct import of hex values when a token exists → **WARN**: "Import from design-tokens instead"

## Output format

```
## UI Review: {file or component name}

### Color Compliance
{PASS | FAIL with violations}

### Typography Compliance  
{PASS | FAIL with violations}

### Component Patterns
{PASS | FAIL with violations}

### Token Usage
{PASS | FAIL with violations}

### Findings
1. **[BLOCK]** ChatBubble.tsx:23 — Cinnamon accent on user message background
   Rule: Cinnamon banned in chat UI (BRAND.md → "Where Cinnamon DOES NOT appear")
   Fix: Use var(--color-soft-black)

---
Verdict: {PASS | NEEDS FIXES}
```
