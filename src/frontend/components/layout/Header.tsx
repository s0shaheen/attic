"use client"

import * as React from "react"
import Link from "next/link"
import { UserMenu } from "./UserMenu"

export interface HeaderProps {
  /** User data for the UserMenu. If null, user is not authenticated. */
  user?: {
    name?: string | null
    email?: string | null
    avatarUrl?: string | null
  } | null
}

/**
 * Application header component.
 *
 * Displays:
 * - Logo/brand on the left
 * - UserMenu on the right (when authenticated)
 * - Sign in link (when not authenticated)
 */
export function Header({ user }: HeaderProps) {
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center">
        {/* Logo */}
        <Link href="/" className="mr-6 flex items-center space-x-2">
          <span className="text-xl font-bold">Attic</span>
        </Link>

        {/* Spacer */}
        <div className="flex-1" />

        {/* User section */}
        <nav className="flex items-center space-x-2">
          {user ? (
            <UserMenu
              name={user.name}
              email={user.email}
              avatarUrl={user.avatarUrl}
            />
          ) : (
            <Link
              href="/auth/login"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              Sign in
            </Link>
          )}
        </nav>
      </div>
    </header>
  )
}
