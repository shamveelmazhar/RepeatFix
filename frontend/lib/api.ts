// Single entry point for data. Uses the real FastAPI backend (docs/API.md) unless
// mock mode is on: NEXT_PUBLIC_USE_MOCKS=true, or no NEXT_PUBLIC_API_URL is set.

import { mockApi } from "./mock";
import type { AssistResponse, FailureMode, GroupBy, JobCard, Metrics, RepeatRow, WorkOrder } from "./types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
export const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true" || !API_URL;

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
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  getCards(): Promise<JobCard[]> {
    if (USE_MOCKS) return mockApi.getCards();
    return request<{ cards: JobCard[] }>("/api/cards?limit=500").then((r) => r.cards);
  },

  getCard(id: string): Promise<JobCard | undefined> {
    if (USE_MOCKS) return mockApi.getCard(id);
    return request<JobCard>(`/api/cards/${encodeURIComponent(id)}`);
  },

  getRepeats(groupBy: GroupBy): Promise<RepeatRow[]> {
    if (USE_MOCKS) return mockApi.getRepeats(groupBy);
    return request<RepeatRow[]>(`/api/repeats?group_by=${groupBy}&min_count=2`);
  },

  getFailureModes(): Promise<FailureMode[]> {
    if (USE_MOCKS) return mockApi.getFailureModes();
    return request<FailureMode[]>("/api/failure-modes");
  },

  getMetrics(): Promise<Metrics> {
    if (USE_MOCKS) return mockApi.getMetrics();
    return request<Metrics>("/api/metrics");
  },

  /** Reads a photographed or scanned log entry and returns it as a job card. */
  async ingestImage(file: File): Promise<JobCard> {
    if (USE_MOCKS) return mockApi.ingestImage();
    const form = new FormData();
    form.append("file", file);
    const r = await request<{ cards: JobCard[] }>("/api/ingest", { method: "POST", body: form });
    if (!r.cards.length) throw new Error("No text could be read from this photo.");
    return r.cards[0];
  },

  assist(faultText: string, asset: string | null, aircraftType: string | null = null): Promise<AssistResponse> {
    if (USE_MOCKS) return mockApi.assist(faultText, asset, aircraftType);
    return request<AssistResponse>("/api/assist", json({ fault_text: faultText, asset, aircraft_type: aircraftType }));
  },

  approve(id: string, workOrder: WorkOrder, approvedBy: string): Promise<{ id: string; status: "approved" }> {
    if (USE_MOCKS) return mockApi.approve(id);
    return request(`/api/work-orders/${encodeURIComponent(id)}/approve`, json({ work_order: workOrder, approved_by: approvedBy }));
  },
};
