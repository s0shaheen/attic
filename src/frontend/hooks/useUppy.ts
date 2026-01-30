"use client";

/**
 * React hook for managing Uppy file uploads.
 *
 * Provides a configured Uppy instance with upload state tracking,
 * presigned URL handling, and lifecycle management.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import Uppy from '@uppy/core';
import XHRUpload from '@uppy/xhr-upload';
import { createUppyInstance, formatBytes } from '@/lib/uppy/config';
import { getPresignedUrl, UploadApiError } from '@/lib/api/uploads';
import { createClient } from '@/lib/supabase/client';

/**
 * Upload state representation.
 */
export interface UploadState {
  /** Current upload status */
  status: 'idle' | 'uploading' | 'complete' | 'error';
  /** Upload progress as percentage (0-100) */
  progress: number;
  /** Number of bytes uploaded */
  bytesUploaded: number;
  /** Total file size in bytes */
  bytesTotal: number;
  /** Filename of the selected file, or null if no file */
  filename: string | null;
  /** Error object if upload failed, or null */
  error: Error | null;
}

/**
 * Result returned when upload completes successfully.
 */
export interface UploadResult {
  /** Unique identifier for this upload */
  uploadId: string;
  /** Storage path where file was uploaded */
  storagePath: string;
  /** Original filename */
  filename: string;
}

/**
 * Options for the useUppy hook.
 */
export interface UseUppyOptions {
  /** Called when upload completes successfully */
  onUploadComplete?: (result: UploadResult) => void;
  /** Called when upload fails */
  onUploadError?: (error: Error) => void;
  /** Called when upload is cancelled */
  onUploadCancel?: () => void;
}

/**
 * Return type for useUppy hook.
 */
export interface UseUppyReturn {
  /** The Uppy instance */
  uppy: Uppy<Record<string, unknown>, Record<string, unknown>> | null;
  /** Current upload state */
  state: UploadState;
  /** Add a file to the upload queue */
  addFile: (file: File) => void;
  /** Start the upload */
  startUpload: () => Promise<void>;
  /** Cancel the current upload */
  cancelUpload: () => void;
  /** Reset the uploader to idle state */
  reset: () => void;
  /** Formatted bytes uploaded string */
  bytesUploadedFormatted: string;
  /** Formatted total bytes string */
  bytesTotalFormatted: string;
}

const initialState: UploadState = {
  status: 'idle',
  progress: 0,
  bytesUploaded: 0,
  bytesTotal: 0,
  filename: null,
  error: null,
};

/**
 * React hook for managing Uppy file uploads with presigned URL support.
 *
 * Creates and manages an Uppy instance with XHR upload plugin,
 * handles presigned URL fetching, and tracks upload state.
 *
 * @param options - Hook options including callbacks
 * @returns Uppy instance, state, and control functions
 *
 * @example
 * ```tsx
 * function UploadComponent() {
 *   const { uppy, state, addFile, startUpload, cancelUpload } = useUppy({
 *     onUploadComplete: (result) => console.log('Upload complete:', result),
 *     onUploadError: (error) => console.error('Upload failed:', error),
 *   });
 *
 *   return (
 *     <div>
 *       <input type="file" onChange={(e) => addFile(e.target.files[0])} />
 *       <button onClick={startUpload}>Upload</button>
 *       {state.status === 'uploading' && (
 *         <div>Progress: {state.progress}%</div>
 *       )}
 *     </div>
 *   );
 * }
 * ```
 */
export function useUppy(options: UseUppyOptions = {}): UseUppyReturn {
  const { onUploadComplete, onUploadError, onUploadCancel } = options;

  const [state, setState] = useState<UploadState>(initialState);
  const uppyRef = useRef<Uppy<Record<string, unknown>, Record<string, unknown>> | null>(null);

  // Store upload metadata between presigned URL fetch and upload completion
  const uploadMetaRef = useRef<{
    uploadId: string;
    storagePath: string;
    filename: string;
  } | null>(null);

  // Initialize Uppy instance
  useEffect(() => {
    const uppy = createUppyInstance();
    uppyRef.current = uppy;

    // Handle file added
    uppy.on('file-added', (file) => {
      setState((prev) => ({
        ...prev,
        filename: file.name ?? null,
        bytesTotal: file.size || 0,
        error: null,
      }));
    });

    // Handle file removed
    uppy.on('file-removed', () => {
      setState((prev) => ({
        ...prev,
        filename: null,
        bytesTotal: 0,
      }));
    });

    // Handle upload progress
    uppy.on('upload-progress', (file, progress) => {
      if (!file || !progress) return;

      const bytesUploaded = progress.bytesUploaded || 0;
      const bytesTotal = progress.bytesTotal || 1;
      const progressPercent = Math.round((bytesUploaded / bytesTotal) * 100);

      setState((prev) => ({
        ...prev,
        status: 'uploading',
        progress: progressPercent,
        bytesUploaded,
        bytesTotal,
      }));
    });

    // Handle upload success
    uppy.on('upload-success', () => {
      const meta = uploadMetaRef.current;
      if (meta) {
        setState((prev) => ({
          ...prev,
          status: 'complete',
          progress: 100,
        }));

        onUploadComplete?.({
          uploadId: meta.uploadId,
          storagePath: meta.storagePath,
          filename: meta.filename,
        });
      }
    });

    // Handle upload error
    uppy.on('upload-error', (_file, error) => {
      const uploadError = error instanceof Error ? error : new Error('Upload failed');
      setState((prev) => ({
        ...prev,
        status: 'error',
        error: uploadError,
      }));
      onUploadError?.(uploadError);
    });

    // Handle restriction error (file type, size, etc.)
    uppy.on('restriction-failed', (_file, error) => {
      const restrictionError = error instanceof Error ? error : new Error('File validation failed');
      setState((prev) => ({
        ...prev,
        status: 'error',
        error: restrictionError,
      }));
      onUploadError?.(restrictionError);
    });

    // Cleanup on unmount
    return () => {
      uppy.cancelAll();
    };
  }, [onUploadComplete, onUploadError]);

  /**
   * Adds a file to the Uppy upload queue.
   */
  const addFile = useCallback((file: File) => {
    const uppy = uppyRef.current;
    if (!uppy) return;

    // Clear any existing files first
    uppy.cancelAll();
    setState(initialState);
    uploadMetaRef.current = null;

    try {
      uppy.addFile({
        name: file.name,
        type: file.type,
        data: file,
        source: 'Local',
      });
    } catch (error) {
      // Uppy throws for restriction violations
      const uploadError = error instanceof Error ? error : new Error('Failed to add file');
      setState((prev) => ({
        ...prev,
        status: 'error',
        error: uploadError,
      }));
      onUploadError?.(uploadError);
    }
  }, [onUploadError]);

  /**
   * Starts the upload process.
   *
   * Fetches a presigned URL from the backend, then initiates the upload.
   */
  const startUpload = useCallback(async () => {
    const uppy = uppyRef.current;
    if (!uppy) return;

    const files = uppy.getFiles();
    if (files.length === 0) {
      const error = new Error('No file selected');
      setState((prev) => ({ ...prev, status: 'error', error }));
      onUploadError?.(error);
      return;
    }

    const file = files[0];
    setState((prev) => ({ ...prev, status: 'uploading', progress: 0 }));

    try {
      // Get access token from Supabase
      const supabase = createClient();
      if (!supabase) {
        throw new Error('Supabase client not available');
      }

      const { data: { session }, error: sessionError } = await supabase.auth.getSession();
      if (sessionError || !session) {
        throw new Error('Not authenticated. Please sign in to upload files.');
      }

      // Get presigned URL from backend
      const filename = file.name ?? 'upload.zip';
      const contentType = file.type || 'application/zip';

      const presignedResponse = await getPresignedUrl(
        {
          filename,
          content_type: contentType,
        },
        session.access_token
      );

      // Store upload metadata for completion callback
      uploadMetaRef.current = {
        uploadId: presignedResponse.upload_id,
        storagePath: presignedResponse.storage_path,
        filename,
      };

      // Configure XHR upload plugin with presigned URL
      uppy.use(XHRUpload, {
        endpoint: presignedResponse.presigned_url,
        method: 'PUT',
        formData: false,
        headers: {
          'Content-Type': contentType,
        },
      });

      // Start the upload
      await uppy.upload();
    } catch (error) {
      let uploadError: Error;

      if (error instanceof UploadApiError) {
        uploadError = error;
      } else if (error instanceof Error) {
        uploadError = error;
      } else {
        uploadError = new Error('Upload failed');
      }

      setState((prev) => ({
        ...prev,
        status: 'error',
        error: uploadError,
      }));
      onUploadError?.(uploadError);
    }
  }, [onUploadError]);

  /**
   * Cancels the current upload.
   */
  const cancelUpload = useCallback(() => {
    const uppy = uppyRef.current;
    if (!uppy) return;

    uppy.cancelAll();
    uploadMetaRef.current = null;
    setState((prev) => ({
      ...prev,
      status: 'idle',
      progress: 0,
      bytesUploaded: 0,
    }));
    onUploadCancel?.();
  }, [onUploadCancel]);

  /**
   * Resets the uploader to initial state.
   */
  const reset = useCallback(() => {
    const uppy = uppyRef.current;
    if (!uppy) return;

    uppy.cancelAll();
    uploadMetaRef.current = null;
    setState(initialState);
  }, []);

  return {
    uppy: uppyRef.current,
    state,
    addFile,
    startUpload,
    cancelUpload,
    reset,
    bytesUploadedFormatted: formatBytes(state.bytesUploaded),
    bytesTotalFormatted: formatBytes(state.bytesTotal),
  };
}
