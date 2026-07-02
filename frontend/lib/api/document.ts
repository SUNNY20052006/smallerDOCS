import { API_BASE_URL, apiJson } from "./client";
import type { DocumentModel } from "@/lib/types/idm";

export async function getDocument(jobId: string): Promise<DocumentModel> {
  return apiJson<DocumentModel>(`/document/${jobId}`);
}

export function getPageImageUrl(jobId: string, pageNumber: number): string {
  return `${API_BASE_URL}/document/${jobId}/page/${pageNumber}/image`;
}
