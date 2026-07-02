"use client";

import type { Editor } from "@tiptap/react";
import { Columns3, Combine, Rows3, Split } from "lucide-react";
import { Button } from "@/components/ui/Button";

export function TableControls({ editor }: { editor: Editor | null }) {
  if (!editor) return null;
  return (
    <div className="flex flex-wrap gap-1 border-b border-border bg-muted/50 p-2">
      <Button title="Add row" onClick={() => editor.chain().focus().addRowAfter().run()}><Rows3 className="h-4 w-4" /></Button>
      <Button title="Add column" onClick={() => editor.chain().focus().addColumnAfter().run()}><Columns3 className="h-4 w-4" /></Button>
      <Button title="Merge cells" onClick={() => editor.chain().focus().mergeCells().run()}><Combine className="h-4 w-4" /></Button>
      <Button title="Split cell" onClick={() => editor.chain().focus().splitCell().run()}><Split className="h-4 w-4" /></Button>
    </div>
  );
}
