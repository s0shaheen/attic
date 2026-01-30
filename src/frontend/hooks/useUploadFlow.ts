"use client";

/**
 * Upload flow state management hook.
 *
 * Manages the complete upload flow state machine:
 * instructions -> uploading -> validating -> scope -> consent -> complete
 *
 * This hook orchestrates the upload page flow, coordinating between
 * file upload, validation, scope selection, and consent capture.
 */

import { useCallback, useReducer } from "react";
import type { Scope } from "@/lib/api/uploads";

// ============================================================================
// Types
// ============================================================================

/**
 * Upload flow step states.
 */
export type UploadFlowStep =
  | "instructions" // Showing export guide
  | "uploading" // File upload in progress
  | "validating" // Validation in progress
  | "invalid" // Validation failed
  | "scope" // Scope selection
  | "consent" // Consent modal open
  | "complete"; // Redirecting to processing

/**
 * Upload error types.
 */
export interface UploadError {
  code: string;
  message: string;
}

/**
 * Result from file upload.
 */
export interface UploadResult {
  uploadId: string;
  storagePath: string;
  filename: string;
}

/**
 * Result from validation.
 */
export interface ValidationResult {
  valid: boolean;
  errorCode: string | null;
  errorMessage: string | null;
  likedCount: number | null;
  favoritedCount: number | null;
  fileHash: string | null;
}

/**
 * Upload flow state.
 */
export interface UploadFlowState {
  step: UploadFlowStep;
  uploadId: string | null;
  filename: string | null;
  storagePath: string | null;
  likedCount: number;
  favoritedCount: number;
  selectedScope: Scope | null;
  totalItems: number;
  tierLimit: number;
  withinLimit: boolean;
  estimatedMinutes: number;
  error: UploadError | null;
  isLoading: boolean;
  flowStartTime: number | null;
}

/**
 * Upload flow actions.
 */
export interface UploadFlowActions {
  /** Start the upload flow (transition from instructions to uploading) */
  startUpload: () => void;
  /** Handle successful upload */
  onUploadComplete: (result: UploadResult) => void;
  /** Handle upload error */
  onUploadError: (error: Error) => void;
  /** Handle upload cancellation */
  onUploadCancel: () => void;
  /** Handle validation completion */
  onValidationComplete: (result: ValidationResult) => void;
  /** Handle validation start */
  onValidationStart: () => void;
  /** Select a scope */
  selectScope: (scope: Scope) => void;
  /** Confirm scope selection and open consent modal */
  confirmScope: () => void;
  /** Give consent (triggers redirect) */
  giveConsent: () => void;
  /** Cancel consent (go back to scope) */
  cancelConsent: () => void;
  /** Retry from error state */
  retry: () => void;
  /** Reset entire flow */
  reset: () => void;
  /** Set loading state */
  setLoading: (loading: boolean) => void;
  /** Set tier limit */
  setTierLimit: (limit: number) => void;
  /** Set estimated minutes */
  setEstimatedMinutes: (minutes: number) => void;
}

// ============================================================================
// Action Types
// ============================================================================

type UploadFlowAction =
  | { type: "START_UPLOAD" }
  | { type: "UPLOAD_COMPLETE"; payload: UploadResult }
  | { type: "UPLOAD_ERROR"; payload: UploadError }
  | { type: "UPLOAD_CANCEL" }
  | { type: "VALIDATION_START" }
  | { type: "VALIDATION_COMPLETE"; payload: ValidationResult }
  | { type: "SELECT_SCOPE"; payload: Scope }
  | { type: "CONFIRM_SCOPE" }
  | { type: "GIVE_CONSENT" }
  | { type: "CANCEL_CONSENT" }
  | { type: "RETRY" }
  | { type: "RESET" }
  | { type: "SET_LOADING"; payload: boolean }
  | { type: "SET_TIER_LIMIT"; payload: number }
  | { type: "SET_ESTIMATED_MINUTES"; payload: number };

// ============================================================================
// Initial State
// ============================================================================

const initialState: UploadFlowState = {
  step: "instructions",
  uploadId: null,
  filename: null,
  storagePath: null,
  likedCount: 0,
  favoritedCount: 0,
  selectedScope: null,
  totalItems: 0,
  tierLimit: 200, // Default free tier limit
  withinLimit: true,
  estimatedMinutes: 0,
  error: null,
  isLoading: false,
  flowStartTime: null,
};

// ============================================================================
// Reducer
// ============================================================================

function uploadFlowReducer(
  state: UploadFlowState,
  action: UploadFlowAction
): UploadFlowState {
  switch (action.type) {
    case "START_UPLOAD":
      return {
        ...state,
        step: "uploading",
        error: null,
        flowStartTime: state.flowStartTime ?? Date.now(),
      };

    case "UPLOAD_COMPLETE":
      return {
        ...state,
        step: "validating",
        uploadId: action.payload.uploadId,
        filename: action.payload.filename,
        storagePath: action.payload.storagePath,
        error: null,
        isLoading: true,
      };

    case "UPLOAD_ERROR":
      return {
        ...state,
        step: "instructions",
        error: action.payload,
        isLoading: false,
      };

    case "UPLOAD_CANCEL":
      return {
        ...state,
        step: "instructions",
        error: null,
        isLoading: false,
      };

    case "VALIDATION_START":
      return {
        ...state,
        step: "validating",
        isLoading: true,
      };

    case "VALIDATION_COMPLETE": {
      const { valid, likedCount, favoritedCount, errorCode, errorMessage } =
        action.payload;

      if (!valid) {
        return {
          ...state,
          step: "invalid",
          error: {
            code: errorCode || "VALIDATION_FAILED",
            message: errorMessage || "Validation failed",
          },
          isLoading: false,
        };
      }

      const liked = likedCount ?? 0;
      const favorited = favoritedCount ?? 0;

      return {
        ...state,
        step: "scope",
        likedCount: liked,
        favoritedCount: favorited,
        error: null,
        isLoading: false,
      };
    }

    case "SELECT_SCOPE": {
      const scope = action.payload;
      let total = 0;
      if (scope === "liked") {
        total = state.likedCount;
      } else if (scope === "favorited") {
        total = state.favoritedCount;
      } else {
        // "both" - use liked count as they overlap
        total = state.likedCount;
      }

      return {
        ...state,
        selectedScope: scope,
        totalItems: total,
        withinLimit: total <= state.tierLimit,
      };
    }

    case "CONFIRM_SCOPE":
      if (!state.selectedScope) {
        return state;
      }
      return {
        ...state,
        step: "consent",
      };

    case "GIVE_CONSENT":
      return {
        ...state,
        step: "complete",
        isLoading: true,
      };

    case "CANCEL_CONSENT":
      return {
        ...state,
        step: "scope",
      };

    case "RETRY":
      return {
        ...initialState,
        tierLimit: state.tierLimit,
        flowStartTime: Date.now(),
      };

    case "RESET":
      return {
        ...initialState,
        tierLimit: state.tierLimit,
      };

    case "SET_LOADING":
      return {
        ...state,
        isLoading: action.payload,
      };

    case "SET_TIER_LIMIT":
      return {
        ...state,
        tierLimit: action.payload,
        withinLimit: state.totalItems <= action.payload,
      };

    case "SET_ESTIMATED_MINUTES":
      return {
        ...state,
        estimatedMinutes: action.payload,
      };

    default:
      return state;
  }
}

// ============================================================================
// Hook
// ============================================================================

/**
 * Hook for managing upload flow state.
 *
 * @returns State and actions for the upload flow
 *
 * @example
 * ```tsx
 * function UploadPage() {
 *   const { state, actions } = useUploadFlow();
 *
 *   return (
 *     <div>
 *       {state.step === 'instructions' && (
 *         <ExportGuide />
 *       )}
 *       {state.step === 'scope' && (
 *         <ScopeSelector
 *           likedCount={state.likedCount}
 *           onSelect={actions.selectScope}
 *         />
 *       )}
 *     </div>
 *   );
 * }
 * ```
 */
export function useUploadFlow(): {
  state: UploadFlowState;
  actions: UploadFlowActions;
} {
  const [state, dispatch] = useReducer(uploadFlowReducer, initialState);

  const actions: UploadFlowActions = {
    startUpload: useCallback(() => {
      dispatch({ type: "START_UPLOAD" });
    }, []),

    onUploadComplete: useCallback((result: UploadResult) => {
      dispatch({ type: "UPLOAD_COMPLETE", payload: result });
    }, []),

    onUploadError: useCallback((error: Error) => {
      dispatch({
        type: "UPLOAD_ERROR",
        payload: { code: "UPLOAD_FAILED", message: error.message },
      });
    }, []),

    onUploadCancel: useCallback(() => {
      dispatch({ type: "UPLOAD_CANCEL" });
    }, []),

    onValidationStart: useCallback(() => {
      dispatch({ type: "VALIDATION_START" });
    }, []),

    onValidationComplete: useCallback((result: ValidationResult) => {
      dispatch({ type: "VALIDATION_COMPLETE", payload: result });
    }, []),

    selectScope: useCallback((scope: Scope) => {
      dispatch({ type: "SELECT_SCOPE", payload: scope });
    }, []),

    confirmScope: useCallback(() => {
      dispatch({ type: "CONFIRM_SCOPE" });
    }, []),

    giveConsent: useCallback(() => {
      dispatch({ type: "GIVE_CONSENT" });
    }, []),

    cancelConsent: useCallback(() => {
      dispatch({ type: "CANCEL_CONSENT" });
    }, []),

    retry: useCallback(() => {
      dispatch({ type: "RETRY" });
    }, []),

    reset: useCallback(() => {
      dispatch({ type: "RESET" });
    }, []),

    setLoading: useCallback((loading: boolean) => {
      dispatch({ type: "SET_LOADING", payload: loading });
    }, []),

    setTierLimit: useCallback((limit: number) => {
      dispatch({ type: "SET_TIER_LIMIT", payload: limit });
    }, []),

    setEstimatedMinutes: useCallback((minutes: number) => {
      dispatch({ type: "SET_ESTIMATED_MINUTES", payload: minutes });
    }, []),
  };

  return { state, actions };
}

export default useUploadFlow;
