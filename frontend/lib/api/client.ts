import type { ErrorObject } from "@/lib/types/errors";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://SnehadriNandi-smallerdocs-backend.hf.space/api/v1";

export class ApiError extends Error {
  error: ErrorObject;
  status: number;

  constructor(error: ErrorObject, status: number) {
    super(error.message);
    this.error = error;
    this.status = status;
  }
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new ApiError(await normalizeError(response), response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function apiBinary(path: string, init: RequestInit): Promise<Response> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new ApiError(await normalizeError(response), response.status);
  }
  return response;
}

async function normalizeError(response: Response): Promise<ErrorObject> {
  try {
    const payload = (await response.json()) as { error?: ErrorObject };
    if (payload.error) {
      return payload.error;
    }
  } catch {
  }
  return {
    code: "PROCESSING_FAILED" as ErrorObject["code"],
    message: `HTTP ${response.status}`,
    userMessage: "Something went wrong.",
    retryable: false,
    details: null,
  };
}
