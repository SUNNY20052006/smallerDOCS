"use client";

import type { ReactNode } from "react";

const ACCEPTED = new Set(["application/pdf", "image/jpeg", "image/png"]);

export function isSupportedFile(file: File): boolean {
  return ACCEPTED.has(file.type) && file.size <= 50 * 1024 * 1024;
}

export function FileTypeGuard({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
