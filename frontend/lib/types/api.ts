import type { ErrorObject } from "./errors";

export type FileType = "pdf" | "image";
export type JobStatus =
  | "uploaded"
  | "queued"
  | "preprocessing"
  | "ocr"
  | "layout_analysis"
  | "reconstruction"
  | "completed"
  | "failed";
export type ExportFormat = "docx" | "html";

export interface UploadResponse {
  jobId: string;
  fileName: string;
  fileType: FileType;
  fileSizeBytes: number;
  status: "uploaded";
}

export interface ProcessResponse {
  jobId: string;
  status: "queued";
}

export interface StatusResponse {
  jobId: string;
  status: JobStatus;
  progress: number;
  currentPage: number | null;
  totalPages: number | null;
  error: ErrorObject | null;
}

export interface TiptapDocument {
  type: "doc";
  content?: TiptapNode[];
}

export interface TiptapNode {
  type: string;
  attrs?: Record<string, unknown>;
  content?: TiptapNode[];
  marks?: TiptapMark[];
  text?: string;
}

export interface TiptapMark {
  type: string;
  attrs?: Record<string, unknown>;
}

export interface ExportRequest {
  format: ExportFormat;
  content: TiptapDocument;
}
