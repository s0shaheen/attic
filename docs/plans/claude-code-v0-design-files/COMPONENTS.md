# Attic — Component Inventory

**Last updated:** 2026-03-16
**Source:** wireframe-chat-v2.html, wireframe-chat-empty.html, wireframe-reveal.html, wireframe-landing-v1.html
**Design system:** Parchment + Ink palette, DM Sans (product) + Crimson Pro (wordmark/marketing only) + DM Mono

---

## How to use this doc

Each component below has: a description, where it appears, its data props, and the design tokens it uses. When building in Next.js + shadcn/ui + Tailwind:

1. Reference this doc for the component API
2. Open the corresponding wireframe HTML file in your browser as the visual target
3. Use design-tokens.ts for all color/spacing/radius values
4. Feed the wireframe screenshot + this spec into v0.dev for rapid generation

---

## Layout components

### AppShell

The top-level layout wrapping sidebar + main content.

- **Where:** Every authenticated page
- **Structure:** Flex row. Sidebar (260px fixed) + main (flex-1)
- **Mobile:** Sidebar collapses to hamburger menu (post-MVP)
- **File:** `components/layout/AppShell.tsx`

### Sidebar

Left navigation panel with conversation history.

- **Where:** All authenticated pages
- **Structure:** Header (wordmark + new chat btn) → grouped conversation list → footer (avatar + name + settings link)
- **Sections grouped by:** Today, Yesterday, Last week, Older
- **Active state:** `background: var(--subtle)`
- **Props:**
  - `conversations: { id, title, meta, updatedAt }[]`
  - `activeConversationId: string | null`
  - `user: { name, email, avatarInitials }`
- **Tokens:** surface bg, border, subtle hover, soft-black for new chat btn
- **File:** `components/layout/Sidebar.tsx`

### ChatHeader

Top bar of the chat area showing conversation title + data summary.

- **Where:** Chat page (active conversation only, not empty state)
- **Structure:** Flex row. Title (DM Sans 15px medium) + meta (DM Mono 11px stone)
- **Props:** `title: string`, `meta: string`
- **File:** `components/chat/ChatHeader.tsx`

### InputArea

Bottom-fixed input for chat messages.

- **Where:** Chat page (both empty state and active)
- **Structure:** Textarea (auto-grow) + send button + hint text
- **Textarea:** bg parchment, border, border-ink on focus, radius-lg, 14px DM Sans
- **Send button:** 40x40px, soft-black bg, parchment text, radius-md
- **Hint:** 11px stone, centered below input
- **Props:** `onSend: (message: string) => void`, `disabled: boolean`, `hint: string`
- **File:** `components/chat/InputArea.tsx`

---

## Message components

### UserBubble

The user's message in chat.

- **Where:** Chat message list
- **Style:** soft-black bg (#2C2926), parchment text, radius-lg, right-aligned, max-width 85%
- **Props:** `content: string`
- **File:** `components/chat/UserBubble.tsx`

### AssistantBubble

The assistant's text response.

- **Where:** Chat message list
- **Style:** white bg, ink text, 0.5px border, radius-lg, left-aligned, max-width 85%
- **Supports:** Bold, inline links (underline only, no color)
- **Props:** `content: string` (rendered as markdown)
- **File:** `components/chat/AssistantBubble.tsx`

### EditorialAside

The agent's "knowing voice" — personality commentary on the data.

- **Where:** Chat message list, between entity cards and chips
- **Style:** DM Sans italic (NOT Crimson Pro — updated from v1), stone color, 2px left border, 8px left padding, max-width 85%
- **Example:** "Heavy on the West Loop — 5 of your 12 restaurant saves are from that neighborhood. You might have a type."
- **Props:** `content: string`
- **File:** `components/chat/EditorialAside.tsx`

### StreamingIndicator

Typing/thinking state while assistant is generating.

- **Where:** Chat message list (replaces assistant bubble during streaming)
- **Style:** White card, 3 pulsing dots (stone color), "Thinking..." label
- **File:** `components/chat/StreamingIndicator.tsx`

---

## Entity card components

### EntityCard

Structured result for a resolved entity (restaurant, book, movie, etc).

- **Where:** Chat responses, expanded entity view, TikTok detail view
- **Structure:** Thumbnail (56px, radius-md) + info column (title, meta, actions, source TikToks)
- **Style:** White bg, 0.5px border, radius-lg, hover: border-hover
- **Variants by type:**
  - **Restaurant:** thumbnail, name, rating stars (cinnamon), neighborhood, save count, creator, open badge, directions link, source TikTok strip
  - **Book:** cover thumbnail (radius-sm for book shape), title, author, save count, creator, Goodreads link
  - **Movie/TV:** poster thumbnail, title, year, TMDB link
  - **Music:** album art, track, artist, Spotify link
  - **Generic:** thumbnail, title, description, source link
- **Props:**
  ```ts
  type EntityType = 'restaurant' | 'book' | 'movie' | 'music' | 'generic';
  interface EntityCardProps {
    type: EntityType;
    thumbnail?: string;
    title: string;
    rating?: number;
    meta: string;
    badges?: { label: string; variant: 'open' | 'count' }[];
    links?: { label: string; url: string }[];
    sourceTikToks?: { id: string; thumbnailColor: string }[];
  }
  ```
- **File:** `components/chat/EntityCard.tsx`

### EntityCardCompact

Smaller version for inline use (e.g., inside TikTok detail view).

- **Where:** TikTok detail → "Entities extracted from this TikTok"
- **Same structure but:** 44px thumbnail, no source TikTok strip
- **File:** Variant of `EntityCard.tsx` via size prop

### SourceTikTokStrip

Row of small TikTok thumbnails showing which videos an entity was extracted from.

- **Where:** Inside EntityCard, inside expanded entity view
- **Structure:** "from" label (10px stone) + row of 28x38px thumbnails + optional "+N" overflow
- **Props:** `tiktoks: { id, thumbnail }[]`, `max?: number`
- **File:** `components/chat/SourceTikTokStrip.tsx`

---

## Collection / grid components

### ThumbnailGrid

Grid of TikTok video thumbnails shown in chat responses.

- **Where:** Chat responses ("The TikToks these came from")
- **Structure:** 3-column grid, 4px gap, radius-lg overflow hidden, max-width 320px
- **Cell:** 9:16 aspect ratio, object-fit cover
- **Last cell can be:** "+N" overflow (subtle bg, stone text, clickable → expanded grid)
- **Props:** `tiktoks: { id, thumbnail }[]`, `max?: number`, `onExpand?: () => void`
- **File:** `components/chat/ThumbnailGrid.tsx`

### TikTokGridView

Full expanded grid of TikTok videos — the "Apple Photos" view.

- **Where:** Expanded TikTok view (triggered from chat "+N" or "View all source TikToks")
- **Structure:** 4-column grid, 6px gap. Each card has:
  - 9:16 visual (object-fit cover)
  - Bottom gradient overlay with creator name + caption (2-line clamp)
  - Top-right entity pips (20px thumbnails of linked entities)
- **Props:** `tiktoks: { id, thumbnail, creator, caption, entities: { thumbnail }[] }[]`
- **Click:** Opens TikTok detail view
- **File:** `components/tiktok/TikTokGridView.tsx`

### TikTokDetailView

Full detail view for a single TikTok video.

- **Where:** Triggered from TikTok grid card click or source strip click
- **Structure:**
  1. Full 9:16 visual (natural aspect ratio, max-width 340px, centered, radius-lg)
  2. Metadata grid: creator, caption, save date, type (liked/favorited), hashtags (mono)
  3. "Entities extracted" section with EntityCard list
- **Props:** `tiktok: { id, thumbnail, creator, caption, savedAt, type, hashtags, entities: EntityCardProps[] }`
- **File:** `components/tiktok/TikTokDetailView.tsx`

### ExpandedEntityView

Full list of all entities from a query, grouped by category.

- **Where:** Triggered from "Show all 12" chip or "+N more" badge
- **Structure:**
  - Header: title + meta + back link
  - Groups: label (e.g., "West Loop · 5 restaurants") → list of expanded entity cards
  - Each entity card includes SourceTikTokStrip
- **Props:** `title, meta, groups: { label, entities: EntityCardProps[] }[]`
- **File:** `components/entity/ExpandedEntityView.tsx`

---

## Interactive components

### SuggestedPromptChips

Follow-up action chips shown after an assistant response.

- **Where:** Chat responses (after entity cards / editorial aside)
- **Structure:** Flex row, wrap, 6px gap
- **Chip style:** DM Sans 12px, white bg, 0.5px border, radius-full (pill), hover: subtle bg + border-hover
- **Behavior:** Click sends the chip text as a new user message
- **Props:** `prompts: string[]`, `onSelect: (prompt: string) => void`
- **File:** `components/chat/SuggestedPromptChips.tsx`

### PromptCards

Data-aware suggested prompts for the empty chat state.

- **Where:** Chat empty state (center of page)
- **Structure:** 2x2 grid of cards. Each card has prompt text (13px medium) + hint (11px stone showing preview data)
- **Style:** White bg, 0.5px border, radius-lg, hover: subtle bg + border-hover
- **Behavior:** Click sends the prompt text as first message
- **Props:** `prompts: { text: string, hint: string }[]`
- **File:** `components/chat/PromptCards.tsx`

### Badge

Small status/count indicator.

- **Where:** Entity cards, sidebar items
- **Variants:**
  - `open`: green bg (#F2F8F3), green text (#2E5E38), green border — "Open now"
  - `count`: subtle bg, stone text — "+9 more restaurants"
  - `rating`: cinnamon-colored star characters — inline with title
- **Props:** `label: string`, `variant: 'open' | 'count'`
- **File:** `components/ui/Badge.tsx` (extend shadcn)

### Chip

Tag/filter pill used throughout.

- **Where:** Chat responses, entity views, search filters
- **Style:** subtle bg (#F0EEE8), stone text, 0.5px border at ink 7% opacity, radius-full
- **Props:** `label: string`, `onClick?: () => void`
- **File:** Extend shadcn Badge component

---

## Reveal page components

### RevealHero

The big stat at the top of the reveal page.

- **Where:** Reveal page, hero section
- **Structure:** Label (12px stone) → number (Crimson Pro 72px 700 cinnamon) → unit (Crimson Pro 20px ink) → date range (DM Mono 13px stone)
- **Props:** `count: number`, `unit: string`, `dateRange: string`
- **File:** `components/reveal/RevealHero.tsx`

### StatGrid

2x2 grid of summary statistics.

- **Where:** Reveal page, chat empty state
- **Structure:** Grid of cards. Each: number (Crimson Pro 32px 600) + label (12px stone)
- **Accent variant:** number in cinnamon (for highlighted stats)
- **Props:** `stats: { value: number, label: string, accent?: boolean }[]`
- **File:** `components/reveal/StatGrid.tsx`

### TopicBar

Ranked topic with horizontal fill bar.

- **Where:** Reveal page "Your top topics"
- **Structure:** Rank number (mono) + name (14px medium) + bar (cinnamon fill, subtle bg) + count (mono)
- **Props:** `rank: number`, `name: string`, `count: number`, `maxCount: number`
- **File:** `components/reveal/TopicBar.tsx`

### CreatorCard

Small card for a top creator in the horizontal scroll strip.

- **Where:** Reveal page "Most saved creators"
- **Structure:** Avatar circle (initials) + name (13px medium) + save count (11px stone)
- **Props:** `name: string`, `initials: string`, `saveCount: number`
- **File:** `components/reveal/CreatorCard.tsx`

### HighlightCard

Featured insight card (most saved video, busiest month, hidden interest).

- **Where:** Reveal page "Highlights" section
- **Structure:** Label (11px stone) + value (Crimson Pro 18px medium) + context (12px stone) + optional thumbnail strip
- **Props:** `label: string`, `value: string`, `context: string`, `thumbnails?: string[]`
- **File:** `components/reveal/HighlightCard.tsx`

---

## Landing page components

### LandingHero

Hero section with headline, subhead, CTA.

- **Where:** Landing page top
- **Structure:** Headline (Crimson Pro 48px 600, -0.03em tracking) + subhead (DM Sans 17px stone) + CTA button (soft-black, radius-lg) + note (12px stone)
- **File:** `components/landing/LandingHero.tsx`

### ProductPreview

Mock chat exchange embedded in the landing page.

- **Where:** Landing page below hero
- **Structure:** Browser chrome dots + simplified chat exchange (user bubble, assistant bubble, 2 entity cards, thumbnail strip)
- **Style:** White card with border, radius-xl, 20px padding
- **File:** `components/landing/ProductPreview.tsx`

### StepCard

"How it works" numbered step.

- **Where:** Landing page, 3-column grid
- **Structure:** Number (Crimson Pro 28px 600 cinnamon) + title (15px medium) + description (13px stone)
- **Props:** `number: number`, `title: string`, `description: string`
- **File:** `components/landing/StepCard.tsx`

### ValuePropCard

Feature description card.

- **Where:** Landing page, 2-column grid
- **Structure:** Title (15px medium) + description (13px stone)
- **Props:** `title: string`, `description: string`
- **File:** `components/landing/ValuePropCard.tsx`

---

## Shared patterns

### Links

- Default: inherit color, underline with border-hover color, darken on hover
- Accent links (.link-accent): cinnamon color, cinnamon-border underline — marketing only
- Never use colored text for links in the product UI

### Typography mapping

| Element | Font | Size | Weight | Color |
|---------|------|------|--------|-------|
| Landing/reveal headline | Crimson Pro (.font-display) | 28–48px | 500–600 | ink |
| Wordmark | Crimson Pro (.wordmark) | 18–20px | 500 | ink |
| Reveal stat number | Crimson Pro (.font-display) | 32–72px | 600–700 | cinnamon or ink |
| In-product page title | DM Sans | 20px | 500 | ink |
| In-product section header | DM Sans | 17px | 500 | ink |
| Chat header title | DM Sans | 15px | 500 | ink |
| Body text / chat messages | DM Sans | 14px | 400 | ink |
| Entity title | DM Sans | 14px | 500 | ink |
| Editorial aside | DM Sans | 14px | 400 italic | stone |
| Metadata / secondary | DM Sans | 11–12px | 400 | stone |
| Chips / badges | DM Sans | 10–12px | 500 | stone |
| Mono (timestamps, data) | DM Mono | 11px | 400 | stone |

### Spacing conventions

- Card padding: 12–16px
- Section gap: 36–48px
- Component gap: 8px (tight), 16px (normal), 24px (loose)
- Message gap: 16px between message groups

### Border conventions

- All cards: 0.5px solid var(--border)
- Hover: border changes to var(--border-hover)
- No shadows except modals (shadow-lg) and focus rings (shadow-focus)
- Editorial aside: 2px solid left border (var(--border))

---

## File structure

```
src/frontend/src/components/
├── ui/                      # shadcn/ui primitives (button, card, dialog, etc.)
│   └── Badge.tsx            # Extended with open/count/rating variants
├── layout/
│   ├── AppShell.tsx
│   └── Sidebar.tsx
├── chat/
│   ├── ChatHeader.tsx
│   ├── InputArea.tsx
│   ├── UserBubble.tsx
│   ├── AssistantBubble.tsx
│   ├── EditorialAside.tsx
│   ├── StreamingIndicator.tsx
│   ├── EntityCard.tsx        # Polymorphic — restaurant/book/movie/music/generic
│   ├── SourceTikTokStrip.tsx
│   ├── ThumbnailGrid.tsx
│   ├── SuggestedPromptChips.tsx
│   └── PromptCards.tsx
├── entity/
│   └── ExpandedEntityView.tsx
├── tiktok/
│   ├── TikTokGridView.tsx
│   └── TikTokDetailView.tsx
├── reveal/
│   ├── RevealHero.tsx
│   ├── StatGrid.tsx
│   ├── TopicBar.tsx
│   ├── CreatorCard.tsx
│   └── HighlightCard.tsx
└── landing/
    ├── LandingHero.tsx
    ├── ProductPreview.tsx
    ├── StepCard.tsx
    └── ValuePropCard.tsx
```

Total: ~28 components. About half are simple (Badge, Chip, Bubble, StatCard). The complex ones are EntityCard (polymorphic), TikTokGridView, ExpandedEntityView, and Sidebar.
