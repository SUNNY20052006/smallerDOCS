import type { TiptapDocument, TiptapNode } from "@/lib/types/api";
import type { Block, DocumentModel, Run, RunMarks } from "@/lib/types/idm";

export function tiptapToIdm(content: TiptapDocument, original: DocumentModel): DocumentModel {
  const blocks = new Map<string, Block>();
  original.pages.forEach((page) => page.blocks.forEach((block) => indexBlock(block, blocks)));
  return {
    ...original,
    pages: [
      {
        ...original.pages[0],
        blocks: (content.content ?? []).flatMap((node) => nodeToBlocks(node, blocks)),
      },
    ],
    metadata: { ...original.metadata, averageConfidence: 1 },
  };
}

function nodeToBlocks(node: TiptapNode, originals: Map<string, Block>): Block[] {
  const attrs = node.attrs ?? {};
  const sourceBlockId = attrs.sourceBlockId as string | null | undefined;
  const original = sourceBlockId ? originals.get(sourceBlockId) : undefined;
  if (node.type === "heading") return [leaf("heading", node, original, { level: attrs.level ?? 1 })];
  if (node.type === "paragraph") return paragraph(node, original);
  if (node.type === "bulletList" || node.type === "orderedList") {
    return [{
      id: sourceBlockId ?? crypto.randomUUID(),
      type: "list",
      bbox: original?.bbox ?? null,
      confidence: 1,
      attrs: { listType: node.type === "bulletList" ? "bullet" : "ordered", startNumber: attrs.start ?? 1 },
      runs: null,
      children: (node.content ?? []).flatMap((child) => nodeToBlocks(child, originals)),
    }];
  }
  if (node.type === "listItem") return [leaf("listItem", { ...node, content: flattenParagraphContent(node) }, original, { indentLevel: attrs.indentLevel ?? 0 })];
  if (node.type === "table") {
    const rows = (node.content ?? []).map((row, rowIndex) => tableRow(row, rowIndex, originals));
    return [{
      id: sourceBlockId ?? crypto.randomUUID(),
      type: "table",
      bbox: original?.bbox ?? null,
      confidence: 1,
      attrs: { rowCount: rows.length, colCount: Math.max(0, ...rows.map((row) => row.children?.length ?? 0)) },
      runs: null,
      children: rows,
    }];
  }
  return [];
}

function paragraph(node: TiptapNode, original?: Block): Block[] {
  const attrs = node.attrs ?? {};
  const content = node.content ?? [];
  const result: Block[] = [];
  const first = content[0];
  const rest = first?.type === "clauseNumber" ? content.slice(1) : content;
  if (first?.type === "clauseNumber") {
    result.push({
      id: (attrs.sourceBlockId as string | undefined) ?? crypto.randomUUID(),
      type: "clauseNumber",
      bbox: original?.bbox ?? null,
      confidence: 1,
      attrs: first.attrs ?? {},
      runs: [run(String(first.attrs?.display ?? ""), original)],
      children: null,
    });
  }
  const role = attrs.blockRole;
  result.push({
    id: (attrs.sourceBlockId as string | undefined) ?? crypto.randomUUID(),
    type: role === "signatureLine" ? "signatureLine" : role === "pageBreak" ? "pageBreak" : "paragraph",
    bbox: original?.bbox ?? null,
    confidence: 1,
    attrs: role === "pageBreak" ? {} : role === "signatureLine" ? { role: attrs.role ?? "signatory" } : { alignment: attrs.textAlign ?? "left", indentLevel: attrs.indentLevel ?? 0 },
    runs: textRuns(rest, original),
    children: null,
  });
  return result;
}

function tableRow(node: TiptapNode, rowIndex: number, originals: Map<string, Block>): Block {
  return {
    id: crypto.randomUUID(),
    type: "tableRow",
    bbox: null,
    confidence: 1,
    attrs: { rowIndex },
    runs: null,
    children: (node.content ?? []).map((cell, colIndex) => tableCell(cell, rowIndex, colIndex, originals)),
  };
}

function tableCell(node: TiptapNode, rowIndex: number, colIndex: number, originals: Map<string, Block>): Block {
  const attrs = node.attrs ?? {};
  const sourceBlockId = attrs.sourceBlockId as string | null | undefined;
  const original = sourceBlockId ? originals.get(sourceBlockId) : undefined;
  return {
    id: sourceBlockId ?? crypto.randomUUID(),
    type: "tableCell",
    bbox: original?.bbox ?? null,
    confidence: 1,
    attrs: { rowIndex, colIndex, rowSpan: attrs.rowspan ?? 1, colSpan: attrs.colspan ?? 1 },
    runs: textRuns(flattenParagraphContent(node), original),
    children: null,
  };
}

function leaf(type: Block["type"], node: TiptapNode, original: Block | undefined, attrs: Record<string, unknown>): Block {
  return {
    id: (node.attrs?.sourceBlockId as string | undefined) ?? crypto.randomUUID(),
    type,
    bbox: original?.bbox ?? null,
    confidence: 1,
    attrs,
    runs: textRuns(node.content ?? [], original),
    children: null,
  };
}

function flattenParagraphContent(node: TiptapNode): TiptapNode[] {
  return (node.content ?? []).flatMap((child) => (child.type === "paragraph" ? child.content ?? [] : [child]));
}

function textRuns(nodes: TiptapNode[], original?: Block): Run[] {
  return nodes.filter((node) => node.type === "text").map((node) => run(node.text ?? "", original, node.marks));
}

function run(text: string, original?: Block, marks = [] as NonNullable<TiptapNode["marks"]>): Run {
  return { id: crypto.randomUUID(), text, bbox: original?.bbox ?? { x: 0, y: 0, width: 0, height: 0 }, confidence: 1, marks: runMarks(marks) };
}

function runMarks(marks: NonNullable<TiptapNode["marks"]>): RunMarks {
  return {
    bold: marks.some((mark) => mark.type === "bold"),
    italic: marks.some((mark) => mark.type === "italic"),
    underline: marks.some((mark) => mark.type === "underline"),
    color: marks.find((mark) => mark.type === "textStyle")?.attrs?.color as string | undefined,
    highlight: marks.find((mark) => mark.type === "highlight")?.attrs?.color as string | undefined,
  };
}

function indexBlock(block: Block, blocks: Map<string, Block>): void {
  blocks.set(block.id, block);
  (block.children ?? []).forEach((child) => indexBlock(child, blocks));
}
