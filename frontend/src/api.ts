import type { Analysis, AnalysisInput, Region } from "./types";
async function request<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, init);
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : response.status === 422
          ? "Check coordinates and year range. Use completed years and at most 60 years."
          : `Request failed (${response.status}). Please try again.`,
    );
  }
  if (!data) throw new Error("The server returned an unreadable response.");
  return data as T;
}
export const searchRegions = (query: string, signal: AbortSignal) =>
  request<{ results: Region[] }>(
    `/regions/search?q=${encodeURIComponent(query)}`,
    { signal },
  );
export const analyze = (body: AnalysisInput, signal: AbortSignal) =>
  request<Analysis>("/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
