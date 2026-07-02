import { apiJson } from "./client";

export async function deleteJob(jobId: string): Promise<void> {
  await apiJson<void>(`/job/${jobId}`, { method: "DELETE" });
}
