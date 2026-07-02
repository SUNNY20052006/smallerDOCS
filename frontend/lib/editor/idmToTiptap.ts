import type { TiptapDocument, TiptapMark, TiptapNode } from "@/lib/types/api";
import type { Block, DocumentModel, Run } from "@/lib/types/idm";

export function idmToTiptap(document: DocumentModel): TiptapDocument {
  return {
    type: "doc",
    content: document.pages.flatMap((page) => page.blocks.flatMap(blockToNode)),
  };
}

function blockToNode(block: Block): TiptapNode[] {
  if (block.type === "heading") {
    return [{ type: "heading", attrs: { level: block.attrs.level ?? 1, sourceBlockId: block.id }, content: runs(block.runs) }];
  }
  if (block.type === "paragraph") {
    return [
      {
        type: "paragraph",
        attrs: {
          sourceBlockId: block.id,
          textAlign: block.attrs.alignment ?? "left",
          indentLevel: block.attrs.indentLevel ?? 0,
        },
        content: runs(block.runs),
      },
    ];
  }
  if (block.type === "clauseNumber") {
    return [
      {
        type: "paragraph",
        attrs: { sourceBlockId: block.id, textAlign: "left", indentLevel: block.attrs.depth ?? 0 },
        content: [
          {
            type: "clauseNumber",
            attrs: {
              numberingStyle: block.attrs.numberingStyle ?? "legal_decimal",
              depth: block.attrs.depth ?? 1,
              display: block.attrs.display ?? firstText(block),
            },
          },
          ...runs(block.runs).filter((node) => node.text !== block.attrs.display),
        ],
      },
    ];
  }
  if (block.type === "signatureLine") {
    return [
      {
        type: "paragraph",
        attrs: { sourceBlockId: block.id, blockRole: "signatureLine", role: block.attrs.role ?? "signatory" },
        content: runs(block.runs),
      },
    ];
  }
  if (block.type === "pageBreak") {
    return [{ type: "paragraph", attrs: { sourceBlockId: block.id, blockRole: "pageBreak" }, content: [] }];
  }
  if (block.type === "list") {
    return [
      {
        type: block.attrs.listType === "ordered" ? "orderedList" : "bulletList",
        attrs: { sourceBlockId: block.id, start: block.attrs.startNumber ?? 1 },
        content: (block.children ?? []).flatMap(blockToNode),
      },
    ];
  }
  if (block.type === "listItem") {
    return [{ type: "listItem", attrs: { sourceBlockId: block.id, indentLevel: block.attrs.indentLevel ?? 0 }, content: [{ type: "paragraph", content: runs(block.runs) }] }];
  }
  if (block.type === "table") {
    return [{ type: "table", attrs: { sourceBlockId: block.id }, content: (block.children ?? []).flatMap(blockToNode) }];
  }
  if (block.type === "tableRow") {
    return [{ type: "tableRow", attrs: { sourceBlockId: block.id }, content: (block.children ?? []).flatMap(blockToNode) }];
  }
  if (block.type === "tableCell") {
    return [
      {
        type: "tableCell",
        attrs: { sourceBlockId: block.id, colspan: block.attrs.colSpan ?? 1, rowspan: block.attrs.rowSpan ?? 1 },
        content: [{ type: "paragraph", content: runs(block.runs) }],
      },
    ];
  }
  return [];
}

function runs(source: Run[] | null): TiptapNode[] {
  return (source ?? []).filter((run) => run.text.length > 0).map((run) => ({ type: "text", text: run.text, marks: marks(run) }));
}

function marks(run: Run): TiptapMark[] | undefined {
  const result: TiptapMark[] = [];
  if (run.marks.bold) result.push({ type: "bold" });
  if (run.marks.italic) result.push({ type: "italic" });
  if (run.marks.underline) result.push({ type: "underline" });
  if (run.marks.color) result.push({ type: "textStyle", attrs: { color: run.marks.color } });
  if (run.marks.highlight) result.push({ type: "highlight", attrs: { color: run.marks.highlight } });
  return result.length ? result : undefined;
}

function firstText(block: Block): string {
  return (block.runs ?? []).map((run) => run.text).join("").split(/\s+/, 1)[0] ?? "";
}
