// Single entry point for data. Uses the real FastAPI backend (docs/API.md) unless
// mock mode is on: NEXT_PUBLIC_USE_MOCKS=true, or no NEXT_PUBLIC_API_URL is set.
// While the backend is still being built, any endpoint it doesn't have yet (404/405 on the
// route itself) falls back to the saved demo data, and the UI says which screens are on it.

import { useSyncExternalStore } from "react";
import { mockApi } from "./mock";
import type { AssistResponse, FailureMode, GroupBy, JobCard, Metrics, RepeatRow, WorkOrder } from "./types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
export const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true" || !API_URL;

/** The backend has no such route yet (FastAPI's own 404/405), as opposed to e.g. "Card not found". */
class MissingEndpoint extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, init);
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.error) message = body.error;
    } catch {
      // keep default message
    }
    if ((res.status === 404 && message === "Not Found") || res.status === 405) throw new MissingEndpoint(message);
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export type Feature = "cards" | "repeats" | "failure-modes" | "metrics" | "ingest" | "assist" | "approve";

// Features currently answered from saved demo data because the backend lacks the endpoint.
let onSample: ReadonlySet<Feature> = new Set();
const listeners = new Set<() => void>();

function markSample(feature: Feature) {
  if (onSample.has(feature)) return;
  onSample = new Set([...onSample, feature]);
  listeners.forEach((l) => l());
}

/** Which features are showing saved demo data while connected to the backend. */
export function useSampleFeatures(): ReadonlySet<Feature> {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => onSample,
    () => onSample,
  );
}

async function live<T>(feature: Feature, call: () => Promise<T>, sample: () => Promise<T>): Promise<T> {
  if (USE_MOCKS) return sample();
  try {
    return await call();
  } catch (err) {
    if (!(err instanceof MissingEndpoint)) throw err;
    markSample(feature);
    return sample();
  }
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  getCards(): Promise<JobCard[]> {
    return live("cards", () => request<{ cards: JobCard[] }>("/api/cards?limit=500").then((r) => r.cards), mockApi.getCards);
  },

  getCard(id: string): Promise<JobCard | undefined> {
    return live("cards", () => request<JobCard>(`/api/cards/${encodeURIComponent(id)}`), () => mockApi.getCard(id));
  },

  getRepeats(groupBy: GroupBy): Promise<RepeatRow[]> {
    return live(
      "repeats",
      () => request<RepeatRow[]>(`/api/repeats?group_by=${groupBy}&min_count=2`),
      () => mockApi.getRepeats(groupBy),
    );
  },

  getFailureModes(): Promise<FailureMode[]> {
    return live("failure-modes", () => request<FailureMode[]>("/api/failure-modes"), mockApi.getFailureModes);
  },

  getMetrics(): Promise<Metrics> {
    return live("metrics", () => request<Metrics>("/api/metrics"), mockApi.getMetrics);
  },

  /** Reads a photographed or scanned log entry and returns it as a job card. */
  ingestImage(file: File): Promise<JobCard> {
    return live(
      "ingest",
      async () => {
        const form = new FormData();
        form.append("file", file);
        const r = await request<{ cards: JobCard[] }>("/api/ingest", { method: "POST", body: form });
        if (!r.cards.length) throw new Error("No text could be read from this photo.");
        return r.cards[0];
      },
      mockApi.ingestImage,
    );
  },

  assist(faultText: string, asset: string | null): Promise<AssistResponse> {
    return live(
      "assist",
      () => request<AssistResponse>("/api/assist", json({ fault_text: faultText, asset })),
      () => mockApi.assist(faultText, asset),
    );
  },

  approve(id: string, workOrder: WorkOrder, approvedBy: string): Promise<{ id: string; status: "approved" }> {
    return live(
      "approve",
      () => request(`/api/work-orders/${encodeURIComponent(id)}/approve`, json({ work_order: workOrder, approved_by: approvedBy })),
      () => mockApi.approve(id),
    );
  },
};
