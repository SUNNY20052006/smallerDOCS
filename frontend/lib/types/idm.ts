export type SourceType = "pdf" | "image";
export type DocumentType = "contract" | "affidavit" | "lease" | "court_filing" | "notice" | "form" | "unknown";
export type BlockType =
  | "heading"
  | "paragraph"
  | "list"
  | "listItem"
  | "table"
  | "tableRow"
  | "tableCell"
  | "clauseNumber"
  | "signatureLine"
  | "pageBreak";

export interface BBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface RunMarks {
  bold: boolean;
  italic: boolean;
  underline: boolean;
  color?: string | null;
  highlight?: string | null;
}

export interface Run {
  id: string;
  text: string;
  bbox: BBox;
  confidence: number;
  marks: RunMarks;
}

export interface Block {
  id: string;
  type: BlockType;
  bbox: BBox | null;
  confidence: number;
  attrs: Record<string, unknown>;
  runs: Run[] | null;
  children: Block[] | null;
}

export interface Page {
  pageNumber: number;
  width: number;
  height: number;
  rotationApplied: 0 | 90 | 180 | 270;
  blocks: Block[];
}

export interface DocumentMetadata {
  detectedDocumentType: DocumentType;
  language: string;
  averageConfidence: number;
}

export interface DocumentModel {
  documentId: string;
  sourceType: SourceType;
  sourceFileName: string;
  pageCount: number;
  createdAt: string;
  pages: Page[];
  metadata: DocumentMetadata;
}
