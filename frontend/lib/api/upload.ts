import { apiJson } from "./client";
import type { UploadResponse } from "@/lib/types/api";

export async function uploadFile(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return apiJson<UploadResponse>("/upload", { method: "POST", body: form });
}
