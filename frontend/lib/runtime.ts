"use client";

// Where the model runs, as the backend reports it in /api/metrics (gpu comes from GPU_LABEL there).
// Read once per page load and shared by the sidebar, Fix a fault and Results.

import { useEffect, useState } from "react";
import { api } from "./api";

export const DEFAULT_GPU = "AMD GPUs via AMD Token Factory";

export interface Runtime {
  gpu: string;
  model: string | null;
}

const FALLBACK: Runtime = { gpu: DEFAULT_GPU, model: null };

let pending: Promise<Runtime> | null = null;

function loadRuntime(): Promise<Runtime> {
  pending ??= api
    .getMetrics()
    .then((m) => ({ gpu: m.gpu || DEFAULT_GPU, model: m.model || null }))
    .catch(() => {
      pending = null; // try again on the next page
      return FALLBACK;
    });
  return pending;
}

export function useRuntime(): Runtime {
  const [runtime, setRuntime] = useState<Runtime>(FALLBACK);
  useEffect(() => {
    let live = true;
    loadRuntime().then((r) => live && setRuntime(r));
    return () => {
      live = false;
    };
  }, []);
  return runtime;
}

/** "Qwen/Qwen2.5-VL-7B-Instruct" reads better as "Qwen2.5-VL-7B-Instruct". */
export function shortModel(model: string | null): string | null {
  return model ? model.split("/").pop() || model : null;
}

/** How the model is served, worded from the GPU label. */
export function servingLabel(gpu: string): string {
  return /token factory/i.test(gpu) ? "AMD Token Factory model API" : "vLLM on ROCm, AMD Developer Cloud";
}
