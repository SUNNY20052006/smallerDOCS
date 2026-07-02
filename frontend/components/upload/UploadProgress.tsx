"use client";

import { Spinner } from "@/components/ui/Spinner";
import type { StatusResponse } from "@/lib/types/api";

export function UploadProgress({ status }: { status: StatusResponse | null }) {
  if (!status) return null;
  const pageText = status.totalPages ? `Page ${status.currentPage ?? 1} of ${status.totalPages}` : "";
  return (
    <div className="w-full rounded-md border border-border bg-card p-4">
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-2 font-medium capitalize text-foreground">
          {status.status !== "completed" && status.status !== "failed" ? <Spinner /> : null}
          {status.status.replace("_", " ")}
        </span>
        <span className="text-muted-foreground">{pageText}</span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
        <div className="h-full bg-primary transition-all" style={{ width: `${status.progress}%` }} />
      </div>
    </div>
  );
}
