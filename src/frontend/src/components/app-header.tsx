"use client";

/**
 * Shared app header with navigation and user menu.
 *
 * Layout:
 *   ┌─────────────────────────────────────────────────┐
 *   │  Logo    [Nav links]   [actions]   [UserMenu]   │
 *   └─────────────────────────────────────────────────┘
 *
 * Used by: /chat, /upload, /settings
 * Page-specific actions (e.g. "New Chat") passed via `actions` prop.
 */

import { useAuth } from "@/lib/auth-context";
import { trackAuthEvent } from "@/lib/posthog";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";

interface AppHeaderProps {
  actions?: ReactNode;
}

export function AppHeader({ actions }: AppHeaderProps) {
  const { user, supabase } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const initial = user?.email?.charAt(0).toUpperCase() ?? "?";

  async function handleSignOut() {
    trackAuthEvent("logout");
    await supabase.auth.signOut();
    router.push("/login");
  }

  const navLinks = [
    { href: "/chat", label: "Chat" },
    { href: "/upload", label: "Upload" },
  ];

  return (
    <header className="flex items-center justify-between border-b border-neutral-800 px-4 py-3">
      <div className="flex items-center gap-6">
        <Link href="/chat" className="text-lg font-semibold text-white">
          Attic
        </Link>
        <nav className="hidden items-center gap-1 sm:flex">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
                pathname === link.href
                  ? "bg-neutral-800 text-white"
                  : "text-neutral-400 hover:bg-neutral-800/50 hover:text-white"
              }`}
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>

      <div className="flex items-center gap-2">
        {actions}

        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-sm font-medium text-white transition-colors hover:bg-blue-500"
              aria-label="User menu"
            >
              {initial}
            </button>
          </DropdownMenu.Trigger>

          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              sideOffset={8}
              className="z-50 w-56 rounded-lg border border-neutral-700 bg-neutral-900 py-1 shadow-xl"
            >
              {user?.email && (
                <>
                  <div className="px-4 py-2">
                    <p className="truncate text-sm text-neutral-400">
                      {user.email}
                    </p>
                  </div>
                  <DropdownMenu.Separator className="h-px bg-neutral-700" />
                </>
              )}

              {/* Mobile nav links */}
              <div className="sm:hidden">
                {navLinks.map((link) => (
                  <DropdownMenu.Item key={link.href} asChild>
                    <Link
                      href={link.href}
                      className="block px-4 py-2 text-sm text-neutral-300 outline-none data-[highlighted]:bg-neutral-800 data-[highlighted]:text-white"
                    >
                      {link.label}
                    </Link>
                  </DropdownMenu.Item>
                ))}
                <DropdownMenu.Separator className="h-px bg-neutral-700" />
              </div>

              <DropdownMenu.Item asChild>
                <Link
                  href="/settings"
                  className="block px-4 py-2 text-sm text-neutral-300 outline-none data-[highlighted]:bg-neutral-800 data-[highlighted]:text-white"
                >
                  Settings
                </Link>
              </DropdownMenu.Item>
              <DropdownMenu.Item
                onSelect={handleSignOut}
                className="block w-full px-4 py-2 text-left text-sm text-neutral-300 outline-none data-[highlighted]:bg-neutral-800 data-[highlighted]:text-white"
              >
                Sign out
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
    </header>
  );
}
