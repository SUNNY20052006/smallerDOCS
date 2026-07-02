import { apiBinary } from "./client";
import type { ExportFormat, TiptapDocument } from "@/lib/types/api";

export async function exportDocument(jobId: string, format: ExportFormat, content: TiptapDocument): Promise<void> {
  const response = await apiBinary(`/export/${jobId}`, {
    method: "POST",
    body: JSON.stringify({ format, content }),
  });
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/);
  const fileName = match?.[1] ?? `document.${format}`;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}
