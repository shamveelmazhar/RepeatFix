// Single entry point for data. Uses the real FastAPI backend (docs/API.md) unless
// mock mode is on: NEXT_PUBLIC_USE_MOCKS=true, or no NEXT_PUBLIC_API_URL is set.

import { mockApi } from "./mock";
import type { AssistResponse, FailureMode, GroupBy, JobCard, Metrics, RepeatRow, WorkOrder } from "./types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
export const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true" || !API_URL;

/** An error the backend answered with. `status` is the HTTP status code. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

/** A fault answer, plus whether it came from the saved demo in this app because the backend couldn't answer. */
export type AssistResult = AssistResponse & { savedDemo?: boolean };

// The longest we wait for a live fault answer before showing the saved demo answer instead.
// The backend answers within about 50 s (falling back to its own saved answer), so this sits above that.
const ASSIST_TIMEOUT_MS = 60_000;

const PHOTO_COMING_SOON = "Photo reading is coming soon. For now, type the fault into the box.";

/** Busy, broken or unreachable: worth showing a saved answer instead of an error. */
function backendUnavailable(err: unknown): boolean {
  if (err instanceof ApiError) return err.status === 429 || err.status >= 500;
  return true; // network failure or timeout: fetch never got an answer
}

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
    throw new ApiError(message, res.status);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

// How long a page waits for the backend's data before showing the saved copy instead.
// Render's free plan takes up to a minute to wake, so don't keep people looking at empty boxes.
const READ_TIMEOUT_MS = 15_000;

/** Reads from the backend, or from the saved demo data when the backend is asleep, down or busy. */
async function readOr<T>(path: string, saved: () => Promise<T>): Promise<T> {
  try {
    return await request<T>(path, { signal: AbortSignal.timeout(READ_TIMEOUT_MS) });
  } catch (err) {
    if (!backendUnavailable(err)) throw err;
    return saved();
  }
}

// The backend hands out at most 500 cards per request.
const CARD_PAGE = 500;

export const api = {
  async getCards(): Promise<JobCard[]> {
    if (USE_MOCKS) return mockApi.getCards();
    const cards: JobCard[] = [];
    for (let offset = 0; ; offset += CARD_PAGE) {
      const page = await readOr<{ total: number; cards: JobCard[] } | null>(
        `/api/cards?limit=${CARD_PAGE}&offset=${offset}`,
        async () => null,
      );
      if (!page) return mockApi.getCards();
      cards.push(...page.cards);
      if (page.cards.length < CARD_PAGE || cards.length >= page.total) return cards;
    }
  },

  getCard(id: string): Promise<JobCard | undefined> {
    if (USE_MOCKS) return mockApi.getCard(id);
    return readOr(`/api/cards/${encodeURIComponent(id)}`, () => mockApi.getCard(id));
  },

  getRepeats(groupBy: GroupBy): Promise<RepeatRow[]> {
    if (USE_MOCKS) return mockApi.getRepeats(groupBy);
    return readOr(`/api/repeats?group_by=${groupBy}&min_count=2`, () => mockApi.getRepeats(groupBy));
  },

  getFailureModes(): Promise<FailureMode[]> {
    if (USE_MOCKS) return mockApi.getFailureModes();
    return readOr("/api/failure-modes", () => mockApi.getFailureModes());
  },

  getMetrics(): Promise<Metrics> {
    if (USE_MOCKS) return mockApi.getMetrics();
    return readOr("/api/metrics", () => mockApi.getMetrics());
  },

  /** Reads a photographed or scanned log entry and returns it as a job card. */
  async ingestImage(file: File): Promise<JobCard> {
    // Neither the backend nor the saved demo can read photos yet, so say so instead of faking a card.
    if (USE_MOCKS) throw new Error(PHOTO_COMING_SOON);
    const form = new FormData();
    form.append("file", file);
    let r: { cards: JobCard[] };
    try {
      r = await request<{ cards: JobCard[] }>("/api/ingest", { method: "POST", body: form });
    } catch (err) {
      // The backend reads typed text only for now and turns photos away with a 4xx.
      if (err instanceof ApiError && err.status < 500) {
        throw new Error(PHOTO_COMING_SOON);
      }
      throw err;
    }
    if (!r.cards.length) throw new Error("No text could be read from this photo.");
    return r.cards[0];
  },

  /**
   * Live answer from the backend. If the backend is rate-limited, failing, unreachable or too slow,
   * falls back to the saved demo answer and marks it `savedDemo` so the screen can say so.
   */
  async assist(faultText: string, asset: string | null, aircraftType: string | null = null): Promise<AssistResult> {
    if (USE_MOCKS) return mockApi.assist(faultText, asset, aircraftType);
    try {
      return await request<AssistResponse>("/api/assist", {
        ...json({ fault_text: faultText, asset, aircraft_type: aircraftType }),
        signal: AbortSignal.timeout(ASSIST_TIMEOUT_MS),
      });
    } catch (err) {
      if (!backendUnavailable(err)) throw err;
      const saved = await mockApi.assist(faultText, asset, aircraftType);
      return { ...saved, savedDemo: true };
    }
  },

  approve(id: string, workOrder: WorkOrder, approvedBy: string): Promise<{ id: string; status: "approved" }> {
    if (USE_MOCKS) return mockApi.approve(id);
    return request(`/api/work-orders/${encodeURIComponent(id)}/approve`, json({ work_order: workOrder, approved_by: approvedBy }));
  },
};
