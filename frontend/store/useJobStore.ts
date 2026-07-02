import { create } from "zustand";
import type { ErrorObject } from "@/lib/types/errors";
import type { JobStatus } from "@/lib/types/api";

interface JobState {
  jobId: string | null;
  status: JobStatus | null;
  progress: number;
  currentPage: number | null;
  totalPages: number | null;
  error: ErrorObject | null;
  setJob: (jobId: string, status: JobStatus) => void;
  setStatus: (state: { status: JobStatus; progress: number; currentPage: number | null; totalPages: number | null; error: ErrorObject | null }) => void;
  reset: () => void;
}

export const useJobStore = create<JobState>((set) => ({
  jobId: null,
  status: null,
  progress: 0,
  currentPage: null,
  totalPages: null,
  error: null,
  setJob: (jobId, status) => set({ jobId, status, progress: 0, error: null }),
  setStatus: (state) => set(state),
  reset: () => set({ jobId: null, status: null, progress: 0, currentPage: null, totalPages: null, error: null }),
}));
