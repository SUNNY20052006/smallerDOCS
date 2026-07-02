"use client";

import { useState } from "react";
import type { Editor } from "@tiptap/react";
import { Button } from "@/components/ui/Button";

export function FindReplacePanel({ editor }: { editor: Editor | null }) {
  const [find, setFind] = useState("");
  const [replace, setReplace] = useState("");
  if (!editor) return null;
  return (
    <div className="flex flex-wrap gap-2 border-b border-border bg-card p-2">
      <input className="h-9 rounded-md border border-input bg-card px-3 text-sm text-foreground placeholder:text-muted-foreground" value={find} onChange={(event) => setFind(event.target.value)} placeholder="Find" />
      <input className="h-9 rounded-md border border-input bg-card px-3 text-sm text-foreground placeholder:text-muted-foreground" value={replace} onChange={(event) => setReplace(event.target.value)} placeholder="Replace" />
      <Button onClick={() => find && editor.commands.insertContent(editor.getText().replaceAll(find, replace))}>Replace all</Button>
    </div>
  );
}
