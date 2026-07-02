"use client";

import type { Editor } from "@tiptap/react";
import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  Bold,
  Columns3,
  Combine,
  Highlighter,
  Italic,
  List,
  ListOrdered,
  Redo2,
  Rows3,
  Split,
  Table,
  Underline,
  Undo2,
} from "lucide-react";
import { Button } from "@/components/ui/Button";

type Alignment = "left" | "center" | "right" | "justify";

const ALIGNMENT_CONTROLS: { value: Alignment; title: string; Icon: typeof AlignLeft }[] = [
  { value: "left", title: "Align left", Icon: AlignLeft },
  { value: "center", title: "Align center", Icon: AlignCenter },
  { value: "right", title: "Align right", Icon: AlignRight },
  { value: "justify", title: "Justify", Icon: AlignJustify },
];

export function EditorToolbar({ editor }: { editor: Editor | null }) {
  if (!editor) return null;
  return (
    <div className="flex flex-wrap items-center gap-1 border-b border-border bg-card p-2">
      <Button title="Bold" onClick={() => editor.chain().focus().toggleBold().run()}><Bold className="h-4 w-4" /></Button>
      <Button title="Italic" onClick={() => editor.chain().focus().toggleItalic().run()}><Italic className="h-4 w-4" /></Button>
      <Button title="Underline" onClick={() => editor.chain().focus().toggleUnderline().run()}><Underline className="h-4 w-4" /></Button>
      <Button title="Highlight" onClick={() => editor.chain().focus().toggleHighlight({ color: "#fff3a3" }).run()}><Highlighter className="h-4 w-4" /></Button>
      <Button title="Bullet list" onClick={() => editor.chain().focus().toggleBulletList().run()}><List className="h-4 w-4" /></Button>
      <Button title="Numbered list" onClick={() => editor.chain().focus().toggleOrderedList().run()}><ListOrdered className="h-4 w-4" /></Button>
      {ALIGNMENT_CONTROLS.map(({ value, title, Icon }) => (
        <Button
          key={value}
          title={title}
          aria-pressed={editor.isActive({ textAlign: value })}
          variant={editor.isActive({ textAlign: value }) ? "primary" : "secondary"}
          onClick={() => editor.chain().focus().setTextAlign(value).run()}
        >
          <Icon className="h-4 w-4" />
        </Button>
      ))}
      <Button title="Insert table" onClick={() => editor.chain().focus().insertTable({ rows: 2, cols: 2, withHeaderRow: false }).run()}><Table className="h-4 w-4" /></Button>
      <Button title="Add row" onClick={() => editor.chain().focus().addRowAfter().run()}><Rows3 className="h-4 w-4" /></Button>
      <Button title="Add column" onClick={() => editor.chain().focus().addColumnAfter().run()}><Columns3 className="h-4 w-4" /></Button>
      <Button title="Merge cells" onClick={() => editor.chain().focus().mergeCells().run()}><Combine className="h-4 w-4" /></Button>
      <Button title="Split cell" onClick={() => editor.chain().focus().splitCell().run()}><Split className="h-4 w-4" /></Button>
      <Button title="Undo" onClick={() => editor.chain().focus().undo().run()}><Undo2 className="h-4 w-4" /></Button>
      <Button title="Redo" onClick={() => editor.chain().focus().redo().run()}><Redo2 className="h-4 w-4" /></Button>
    </div>
  );
}
