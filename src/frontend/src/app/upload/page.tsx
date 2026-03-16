"use client";

import { AppHeader } from "@/components/app-header";
import { useAuth } from "@/lib/auth-context";
import Uppy from "@uppy/core";
import DragDrop from "@uppy/drag-drop";
import ProgressBar from "@uppy/progress-bar";
import XHRUpload from "@uppy/xhr-upload";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import "@uppy/core/dist/style.min.css";
import "@uppy/drag-drop/dist/style.min.css";
import "@uppy/progress-bar/dist/style.min.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type UploadState = "idle" | "uploading" | "processing" | "success" | "error";

export default function UploadPage() {
  const [state, setState] = useState<UploadState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const dragDropRef = useRef<HTMLDivElement>(null);
  const progressRef = useRef<HTMLDivElement>(null);
  const uppyRef = useRef<Uppy | null>(null);
  const router = useRouter();
  const { supabase } = useAuth();

  const getAccessToken = useCallback(async (): Promise<string | null> => {
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token ?? null;
  }, [supabase]);

  useEffect(() => {
    const uppy = new Uppy({
      restrictions: {
        maxNumberOfFiles: 1,
        allowedFileTypes: [".zip"],
      },
      autoProceed: false,
    });

    uppyRef.current = uppy;

    // Install plugins once DOM refs are ready
    if (dragDropRef.current) {
      uppy.use(DragDrop, { target: dragDropRef.current });
    }
    if (progressRef.current) {
      uppy.use(ProgressBar, { target: progressRef.current, hideAfterFinish: false });
    }

    // When a file is added, start the upload flow
    uppy.on("file-added", async () => {
      setState("uploading");
      setErrorMessage(null);
      setUploadProgress(0);

      const token = await getAccessToken();
      if (!token) {
        setState("error");
        setErrorMessage("Not authenticated. Please log in.");
        uppy.cancelAll();
        return;
      }

      try {
        // Step 1: Get presigned URL
        const file = uppy.getFiles()[0];
        const presignedRes = await fetch(`${API_URL}/api/uploads/presigned-url`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            filename: file.name,
            content_type: file.type || "application/zip",
          }),
        });

        if (!presignedRes.ok) {
          throw new Error(`Failed to get upload URL (${presignedRes.status})`);
        }

        const { presigned_url, upload_id, storage_path } = await presignedRes.json();

        // Step 2: Configure XHR upload to use the presigned URL
        uppy.use(XHRUpload, {
          endpoint: presigned_url,
          method: "PUT",
          headers: { "Content-Type": file.type || "application/zip" },
          formData: false,
        });

        // Store metadata for step 3
        uppy.setMeta({ upload_id, storage_path, token });
        uppy.upload();
      } catch (err) {
        setState("error");
        setErrorMessage(err instanceof Error ? err.message : "Upload failed");
        uppy.cancelAll();
      }
    });

    uppy.on("progress", (progress: number) => {
      setUploadProgress(progress);
    });

    uppy.on("complete", async (result) => {
      if (!result.successful?.length) return;

      // Step 3: Trigger pipeline processing
      setState("processing");
      const meta = uppy.getState().meta as Record<string, string>;

      try {
        const processRes = await fetch(`${API_URL}/api/uploads/process`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${meta.token}`,
          },
          body: JSON.stringify({
            upload_id: meta.upload_id,
            storage_path: meta.storage_path,
          }),
        });

        if (!processRes.ok) {
          throw new Error(`Failed to trigger processing (${processRes.status})`);
        }

        setState("success");
      } catch (err) {
        setState("error");
        setErrorMessage(err instanceof Error ? err.message : "Processing trigger failed");
      }
    });

    uppy.on("error", (error: Error) => {
      setState("error");
      setErrorMessage(error.message || "Upload failed");
    });

    return () => {
      uppy.destroy();
    };
  }, [getAccessToken]);

  return (
    <div className="flex min-h-screen flex-col bg-neutral-950">
      <AppHeader />
      <div className="flex flex-1 flex-col items-center justify-center px-4">
      <div className="w-full max-w-lg">
        <h1 className="mb-2 text-center text-2xl font-semibold text-white">
          Upload your TikTok data
        </h1>
        <p className="mb-8 text-center text-sm text-neutral-400">
          Go to TikTok Settings &rarr; Privacy &rarr; Download your data, then
          drop the ZIP file here.
        </p>

        {state === "idle" && (
          <>
            <div
              ref={dragDropRef}
              className="rounded-xl border-2 border-dashed border-neutral-700 bg-neutral-900 p-12 text-center transition-colors hover:border-blue-500"
            />
            <div ref={progressRef} className="mt-4" />
          </>
        )}

        {state === "uploading" && (
          <div className="rounded-xl border border-neutral-700 bg-neutral-900 p-8 text-center">
            <div className="mx-auto mb-4 h-2 w-full overflow-hidden rounded-full bg-neutral-800">
              <div
                className="h-full rounded-full bg-blue-600 transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <p className="text-sm text-neutral-300">
              Uploading... {uploadProgress}%
            </p>
          </div>
        )}

        {state === "processing" && (
          <div className="rounded-xl border border-neutral-700 bg-neutral-900 p-8 text-center">
            <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-neutral-600 border-t-blue-500" />
            <p className="text-sm text-neutral-300">
              Starting pipeline processing...
            </p>
          </div>
        )}

        {state === "success" && (
          <div className="rounded-xl border border-green-800 bg-green-950/30 p-8 text-center">
            <p className="mb-4 text-lg font-medium text-green-400">
              Upload complete!
            </p>
            <p className="mb-6 text-sm text-neutral-400">
              Your data is being processed. This takes a few minutes. You can
              start chatting while it processes.
            </p>
            <button
              onClick={() => router.push("/chat")}
              className="rounded-xl bg-blue-600 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-blue-500"
            >
              Go to Chat
            </button>
          </div>
        )}

        {state === "error" && (
          <div className="rounded-xl border border-red-800 bg-red-950/30 p-8 text-center">
            <p className="mb-4 text-sm text-red-400">
              {errorMessage || "Something went wrong"}
            </p>
            <button
              onClick={() => {
                setState("idle");
                setErrorMessage(null);
                uppyRef.current?.cancelAll();
              }}
              className="rounded-xl border border-neutral-700 px-6 py-3 text-sm text-neutral-300 transition-colors hover:bg-neutral-800"
            >
              Try Again
            </button>
          </div>
        )}
      </div>
      </div>
    </div>
  );
}
