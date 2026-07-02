"use client";

import { DocumentEditor } from "@/components/editor/DocumentEditor";
import type { TiptapDocument } from "@/lib/types/api";
import type { DocumentModel } from "@/lib/types/idm";
import { OriginalDocumentPane } from "./OriginalDocumentPane";

export function ComparisonLayout({ document, content }: { document: DocumentModel; content: TiptapDocument }) {
  return (
    <div className="grid h-full min-h-0 grid-cols-[minmax(320px,42%)_1fr] bg-card">
      <OriginalDocumentPane document={document} />
      <DocumentEditor content={content} />
    </div>
  );
}
