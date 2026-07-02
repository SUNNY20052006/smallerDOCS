"use client";

import { useEffect } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import TextStyle from "@tiptap/extension-text-style";
import Color from "@tiptap/extension-color";
import Highlight from "@tiptap/extension-highlight";
import TextAlign from "@tiptap/extension-text-align";
import Table from "@tiptap/extension-table";
import TableRow from "@tiptap/extension-table-row";
import TableCell from "@tiptap/extension-table-cell";
import TableHeader from "@tiptap/extension-table-header";
import Placeholder from "@tiptap/extension-placeholder";
import type { TiptapDocument } from "@/lib/types/api";
import { ClauseNumber } from "@/lib/editor/extensions/clauseNumber";
import { SourceBlockId } from "@/lib/editor/extensions/sourceBlockId";
import { useComparisonStore } from "@/store/useComparisonStore";
import { useDocumentStore } from "@/store/useDocumentStore";
import { EditorToolbar } from "./EditorToolbar";
import { FindReplacePanel } from "./FindReplacePanel";

export function DocumentEditor({ content }: { content: TiptapDocument }) {
  const setTiptapDoc = useDocumentStore((state) => state.setTiptapDoc);
  const activeSourceBlockId = useComparisonStore((state) => state.activeSourceBlockId);
  const setActiveSourceBlockId = useComparisonStore((state) => state.setActiveSourceBlockId);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: { levels: [1, 2, 3] } }),
      Underline,
      TextStyle,
      Color,
      Highlight.configure({ multicolor: true }),
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      Table.configure({ resizable: true }),
      TableRow,
      TableCell,
      TableHeader,
      Placeholder.configure({ placeholder: " " }),
      ClauseNumber,
      SourceBlockId,
    ],
    content,
    immediatelyRender: false,
    onUpdate: ({ editor }) => setTiptapDoc(editor.getJSON() as TiptapDocument),
    editorProps: {
      attributes: { class: "prose prose-slate max-w-none min-h-full focus:outline-none p-8" },
      handleClickOn: (_view, _pos, node) => {
        const id = node.attrs.sourceBlockId as string | null | undefined;
        if (id) setActiveSourceBlockId(id);
        return false;
      },
    },
  });

  useEffect(() => {
    if (!editor || !activeSourceBlockId) return;
    const element = document.querySelector(`[data-source-block-id="${activeSourceBlockId}"]`);
    element?.scrollIntoView({ behavior: "smooth", block: "center" });
    element?.classList.add("source-highlight");
    const timeout = window.setTimeout(() => element?.classList.remove("source-highlight"), 1200);
    return () => window.clearTimeout(timeout);
  }, [activeSourceBlockId, editor]);

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col border-l border-border bg-card">
      <div className="flex-none bg-card">
        <EditorToolbar editor={editor} />
        <FindReplacePanel editor={editor} />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}
