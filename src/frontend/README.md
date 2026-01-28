# Attic Frontend

Next.js 14 frontend for the Attic personal TikTok analytics platform.

## Tech Stack

- **Next.js 14** with App Router
- **TypeScript** (strict mode)
- **Tailwind CSS** with warm minimal theme
- **shadcn/ui** component library (Button, Card, Input)
- **TanStack Query** for server state management
- **React Hook Form** with Zod resolver for form validation

## Getting Started

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

3. Open [http://localhost:3000](http://localhost:3000)

## Available Scripts

| Script          | Description                          |
| --------------- | ------------------------------------ |
| `npm run dev`   | Start development server on port 3000 |
| `npm run build` | Create production build              |
| `npm start`     | Start production server              |
| `npm run lint`  | Run ESLint                           |
| `npm run typecheck` | Run TypeScript compiler (no emit) |

## Project Structure

```
src/frontend/
├── app/                    # App Router pages and layout
│   ├── layout.tsx          # Root layout with providers
│   ├── page.tsx            # Landing page
│   └── globals.css         # Global styles with Tailwind
├── components/
│   ├── providers.tsx       # Client providers (QueryClientProvider)
│   └── ui/                 # shadcn/ui components
│       ├── button.tsx
│       ├── card.tsx
│       └── input.tsx
├── lib/
│   ├── query-client.ts     # TanStack Query client configuration
│   └── utils.ts            # Utility functions (cn)
├── tailwind.config.ts      # Tailwind CSS configuration
├── tsconfig.json           # TypeScript configuration (strict mode)
├── next.config.js          # Next.js configuration
└── components.json         # shadcn/ui configuration
```

## Code Conventions

- Server components by default; use `"use client"` directive for client components
- Use `@/` path alias for imports from the project root
- Use `cn()` utility for conditional class names
- Zod schemas for runtime validation
