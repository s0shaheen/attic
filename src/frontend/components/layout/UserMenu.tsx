"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { useQueryClient } from "@tanstack/react-query"
import { LogOut, Loader2 } from "lucide-react"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { signOut } from "@/lib/supabase/auth"

export interface UserMenuProps {
  /** User's display name */
  name?: string | null
  /** User's email address */
  email?: string | null
  /** User's avatar URL */
  avatarUrl?: string | null
  /** Optional className for the trigger button */
  className?: string
}

/**
 * Gets initials from a name for avatar fallback.
 * Returns first letter of first and last name, or first two letters if single name.
 */
function getInitials(name: string | null | undefined): string {
  if (!name) return "U"

  const parts = name.trim().split(" ").filter(Boolean)
  if (parts.length === 0) return "U"
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase()
  }

  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

/**
 * UserMenu component with sign out functionality.
 *
 * Displays user avatar with dropdown menu containing:
 * - User info (name, email)
 * - Sign out button
 *
 * Sign out:
 * 1. Shows loading state
 * 2. Clears Supabase session
 * 3. Clears React Query cache
 * 4. Redirects to login page
 *
 * Errors are handled gracefully - user will be signed out even if
 * the Supabase call fails.
 */
export function UserMenu({ name, email, avatarUrl, className }: UserMenuProps) {
  const router = useRouter()
  const queryClient = useQueryClient()
  const [isSigningOut, setIsSigningOut] = React.useState(false)

  async function handleSignOut() {
    try {
      setIsSigningOut(true)

      // Call Supabase sign out
      const { error } = await signOut()

      // Log errors but don't block sign out flow
      if (error) {
        console.error("[UserMenu] Sign out had error, but continuing:", error.message)
      }

      // Clear all cached data from React Query
      queryClient.clear()

      // Redirect to login page
      router.push("/auth/login")
      router.refresh()
    } catch (err) {
      // Even on unexpected errors, try to redirect
      console.error("[UserMenu] Unexpected sign out error:", err)
      router.push("/auth/login")
      router.refresh()
    } finally {
      // Reset loading state (though usually we've navigated away)
      setIsSigningOut(false)
    }
  }

  const displayName = name || email || "User"
  const initials = getInitials(name || email)

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className={`relative h-9 w-9 rounded-full ${className ?? ""}`}
          disabled={isSigningOut}
          aria-label="User menu"
        >
          <Avatar className="h-9 w-9">
            {avatarUrl && <AvatarImage src={avatarUrl} alt={displayName} />}
            <AvatarFallback className="text-xs">{initials}</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56" align="end" forceMount>
        <DropdownMenuLabel className="font-normal">
          <div className="flex flex-col space-y-1">
            {name && (
              <p className="text-sm font-medium leading-none">{name}</p>
            )}
            {email && (
              <p className="text-xs leading-none text-muted-foreground">
                {email}
              </p>
            )}
            {!name && !email && (
              <p className="text-sm font-medium leading-none">My Account</p>
            )}
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={handleSignOut}
          disabled={isSigningOut}
          className="cursor-pointer text-destructive focus:text-destructive"
        >
          {isSigningOut ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <LogOut className="mr-2 h-4 w-4" />
          )}
          {isSigningOut ? "Signing out..." : "Sign out"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
