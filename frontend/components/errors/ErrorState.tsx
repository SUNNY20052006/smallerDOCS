import type { ErrorObject } from "@/lib/types/errors";

export function ErrorState({ error }: { error: ErrorObject }) {
  return (
    <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
      <p className="font-medium">{error.userMessage}</p>
      <p className="mt-1 opacity-80">{error.code}</p>
    </div>
  );
}
