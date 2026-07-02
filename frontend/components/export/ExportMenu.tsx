"use client";

import { Download } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { exportDocument } from "@/lib/api/export";
import type { ExportFormat } from "@/lib/types/api";
import { useDocumentStore } from "@/store/useDocumentStore";

export function ExportMenu({ jobId }: { jobId: string }) {
  const tiptapDoc = useDocumentStore((state) => state.tiptapDoc);
  const runExport = async (format: ExportFormat) => {
    if (tiptapDoc) await exportDocument(jobId, format, tiptapDoc);
  };
  return (
    <div className="flex gap-2">
      <Button variant="primary" disabled={!tiptapDoc} onClick={() => void runExport("docx")}><Download className="h-4 w-4" />DOCX</Button>
      <Button disabled={!tiptapDoc} onClick={() => void runExport("html")}><Download className="h-4 w-4" />HTML</Button>
    </div>
  );
}
