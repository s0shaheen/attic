"use client"

import * as React from "react"
import { useState } from "react"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { signOut } from "@/lib/supabase/auth"
import { createClient } from "@/lib/supabase/client"

const CONFIRMATION_TEXT = "DELETE"

interface DeleteAccountModalProps {
  /**
   * Optional trigger element. If not provided, a default button is shown.
   */
  trigger?: React.ReactNode
}

/**
 * Modal component for account deletion confirmation.
 *
 * Requires user to type "DELETE" to confirm the action.
 * After successful deletion, signs out the user and redirects to home.
 */
export function DeleteAccountModal({ trigger }: DeleteAccountModalProps) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [confirmText, setConfirmText] = useState("")
  const [isDeleting, setIsDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isConfirmed = confirmText === CONFIRMATION_TEXT

  const handleDelete = async () => {
    if (!isConfirmed) return

    setIsDeleting(true)
    setError(null)

    try {
      const supabase = createClient()
      if (!supabase) {
        setError("Unable to connect to authentication service")
        setIsDeleting(false)
        return
      }

      // Get the current session for the auth token
      const {
        data: { session },
      } = await supabase.auth.getSession()

      if (!session?.access_token) {
        setError("You must be logged in to delete your account")
        setIsDeleting(false)
        return
      }

      // Call the backend deletion endpoint
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/user/me`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${session.access_token}`,
            "Content-Type": "application/json",
          },
        }
      )

      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(
          data?.detail?.detail || data?.detail || "Failed to delete account"
        )
      }

      // Sign out the user
      await signOut()

      // Close modal and redirect
      setOpen(false)
      router.push("/")
      router.refresh()
    } catch (err) {
      console.error("[DeleteAccountModal] Error:", err)
      setError(
        err instanceof Error ? err.message : "An unexpected error occurred"
      )
      setIsDeleting(false)
    }
  }

  const handleOpenChange = (newOpen: boolean) => {
    if (!isDeleting) {
      setOpen(newOpen)
      if (!newOpen) {
        // Reset state when closing
        setConfirmText("")
        setError(null)
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="destructive">Delete Account</Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle className="text-destructive">Delete Account</DialogTitle>
          <DialogDescription>
            This action cannot be undone. This will permanently delete your
            account and remove all your data from our servers.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              To confirm, type{" "}
              <span className="font-mono font-bold">{CONFIRMATION_TEXT}</span>{" "}
              below:
            </p>
            <Input
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder={CONFIRMATION_TEXT}
              disabled={isDeleting}
              autoComplete="off"
              data-testid="delete-confirmation-input"
            />
          </div>

          {error && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={isDeleting}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={!isConfirmed || isDeleting}
            data-testid="confirm-delete-button"
          >
            {isDeleting ? "Deleting..." : "Delete Account"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
