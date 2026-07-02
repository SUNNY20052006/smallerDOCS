"use client";

import { useEffect, useState } from "react";
import { ErrorState } from "@/components/errors/ErrorState";
import { ExportMenu } from "@/components/export/ExportMenu";
import { ComparisonLayout } from "@/components/comparison/ComparisonLayout";
import { getDocument } from "@/lib/api/document";
import { idmToTiptap } from "@/lib/editor/idmToTiptap";
import type { ErrorObject } from "@/lib/types/errors";
import type { DocumentModel } from "@/lib/types/idm";
import { useDocumentStore } from "@/store/useDocumentStore";

export function EditorWorkspace({ jobId }: { jobId: string }) {
  const setDocument = useDocumentStore((state) => state.setDocument);
  const tiptapDoc = useDocumentStore((state) => state.tiptapDoc);
  const [document, setLocalDocument] = useState<DocumentModel | null>(null);
  const [error, setError] = useState<ErrorObject | null>(null);

  useEffect(() => {
    void getDocument(jobId)
      .then((doc) => {
        const content = idmToTiptap(doc);
        setLocalDocument(doc);
        setDocument(doc, content);
      })
      .catch((caught) => setError((caught as { error?: ErrorObject }).error ?? null));
  }, [jobId, setDocument]);

  if (error) return <main className="p-6"><ErrorState error={error} /></main>;
  if (!document || !tiptapDoc) return <main className="p-6 text-sm text-muted-foreground">Loading document...</main>;

  return (
    <main className="flex h-screen flex-col overflow-hidden">
      <div className="z-10 flex flex-none items-center justify-between border-b border-border bg-card px-4 py-3">
        <div>
          <h1 className="text-base font-semibold text-foreground">{document.sourceFileName}</h1>
          <p className="text-xs text-muted-foreground">{document.pageCount} page{document.pageCount === 1 ? "" : "s"}</p>
        </div>
        <ExportMenu jobId={jobId} />
      </div>
      <div className="min-h-0 flex-1">
        <ComparisonLayout document={document} content={tiptapDoc} />
      </div>
    </main>
  );
}
