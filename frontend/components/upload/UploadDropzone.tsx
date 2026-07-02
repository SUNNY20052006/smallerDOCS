"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Upload } from "lucide-react";
import { ErrorState } from "@/components/errors/ErrorState";
import { UploadProgress } from "./UploadProgress";
import { isSupportedFile } from "./FileTypeGuard";
import { startProcessing, pollStatus } from "@/lib/api/process";
import { uploadFile } from "@/lib/api/upload";
import type { StatusResponse } from "@/lib/types/api";
import type { ErrorObject } from "@/lib/types/errors";

export function UploadDropzone() {
  const router = useRouter();
  const [error, setError] = useState<ErrorObject | null>(null);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [busy, setBusy] = useState(false);

  const handleFile = useCallback(async (file: File) => {
    setError(null);
    if (!isSupportedFile(file)) {
      setError({ code: "UNSUPPORTED_FILE_TYPE" as ErrorObject["code"], message: "Unsupported file", userMessage: "Upload a PDF, JPG, or PNG under 50 MB.", retryable: false });
      return;
    }
    setBusy(true);
    try {
      const upload = await uploadFile(file);
      await startProcessing(upload.jobId);
      let next: StatusResponse;
      do {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        next = await pollStatus(upload.jobId);
        setStatus(next);
      } while (!["completed", "failed"].includes(next.status));
      if (next.status === "failed" && next.error) {
        setError(next.error);
      } else {
        router.push(`/editor/${upload.jobId}`);
      }
    } catch (caught) {
      setError((caught as { error?: ErrorObject }).error ?? { code: "UPLOAD_FAILED" as ErrorObject["code"], message: String(caught), userMessage: "The upload failed.", retryable: false });
    } finally {
      setBusy(false);
    }
  }, [router]);

  useEffect(() => {
    const onDragOver = (e: DragEvent) => e.preventDefault();
    const onDrop = (e: DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer?.files[0];
      if (file) void handleFile(file);
    };
    document.addEventListener("dragover", onDragOver);
    document.addEventListener("drop", onDrop);
    return () => {
      document.removeEventListener("dragover", onDragOver);
      document.removeEventListener("drop", onDrop);
    };
  }, [handleFile]);

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4">
      <label
        className="flex min-h-72 cursor-pointer flex-col items-center justify-center rounded-md border border-dashed border-border bg-card px-8 text-center transition hover:border-ring hover:bg-accent/50"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          const file = event.dataTransfer.files[0];
          if (file) void handleFile(file);
        }}
      >
        <Upload className="mb-4 h-8 w-8 text-muted-foreground" aria-hidden />
        <span className="text-lg font-semibold text-foreground">Drop a document</span>
        <span className="mt-1 text-sm text-muted-foreground">PDF, JPG, or PNG</span>
        <input className="sr-only" type="file" accept="application/pdf,image/jpeg,image/png" disabled={busy} onChange={(event) => event.target.files?.[0] && void handleFile(event.target.files[0])} />
      </label>
      <UploadProgress status={status} />
      {error ? <ErrorState error={error} /> : null}
    </div>
  );
}
