import { apiJson } from "./client";
import type { ProcessResponse, StatusResponse } from "@/lib/types/api";

export async function startProcessing(jobId: string): Promise<ProcessResponse> {
  return apiJson<ProcessResponse>(`/process/${jobId}`, { method: "POST" });
}

export async function pollStatus(jobId: string): Promise<StatusResponse> {
  return apiJson<StatusResponse>(`/status/${jobId}`);
}
