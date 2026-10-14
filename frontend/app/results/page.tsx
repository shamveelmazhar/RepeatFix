"use client";

import { useEffect, useState } from "react";
import { ChipIcon } from "@/components/icons";
import { Panel, Skeleton } from "@/components/ui";
import { USE_MOCKS, api } from "@/lib/api";
import type { Metrics } from "@/lib/types";

const STEPS = [
  {
    title: "Read the logs",
    body: "Messy write-ups, abbreviations and photos of log entries are turned into clean job cards: aircraft, ATA chapter, component, symptom, fix, parts, downtime.",
  },
  {
    title: "Find the repeats",
    body: "Job cards are grouped by aircraft and problem. Counts, days between failures and downtime are plain arithmetic, so every number can be checked.",
  },
  {
    title: "Help with the next fault",
    body: "A new fault is matched to the closest past fixes and the FAA procedure that applies. Likely causes are listed with the records behind them.",
  },
  {
    title: "A person decides",
    body: "RepeatFix only drafts the work order. A supervisor edits and approves it before anything is issued.",
  },
];

const SOURCES = [
  "FAA Service Difficulty Reports (malfunction and defect reports)",
  "NASA ASRS maintenance reports",
  "FAA AC 43.13-1B: Acceptable Methods, Techniques, and Practices",
  "FAA Aviation Maintenance Technician Handbook",
];

export default function ResultsPage() {
  const [m, setM] = useState<Metrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getMetrics()
      .then(setM)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load results."));
  }, []);

  const pct = (v: number | null) => (v === null ? null : `${Math.round(v * 100)}%`);

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Results</h1>
        <p className="mt-2 max-w-2xl text-lg text-muted">
          Measured numbers, not claims. How accurate RepeatFix is, what it found, and what it costs to run.
        </p>
      </header>

      {error && (
        <p role="alert" className="rounded-xl border border-critical/30 bg-critical-soft p-4 text-critical">
          {error}
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Metric
          loading={!m}
          label="Reading accuracy"
          value={m && pct(m.extraction_field_accuracy)}
          sub={m ? `Fields read correctly on ${m.labelled_cards} hand-checked job cards` : ""}
        />
        <Metric loading={!m} label="Job cards processed" value={m && m.cards_processed.toLocaleString()} />
        <Metric loading={!m} label="Repeat problems found" value={m && String(m.repeat_groups_found)} />
        <Metric
          loading={!m}
          label="Time to answer a fault"
          value={m && (m.p50_latency_ms === null ? null : `${(m.p50_latency_ms / 1000).toFixed(1)} s`)}
          sub="Typical (median) time"
        />
        <Metric loading={!m} label="Generation speed" value={m && (m.tokens_per_s === null ? null : `${Math.round(m.tokens_per_s)} tokens/s`)} />
        <Metric
          loading={!m}
          label="Cost per 100 job cards"
          value={m && (m.cost_per_100_cards_usd === null ? null : `$${m.cost_per_100_cards_usd.toFixed(2)}`)}
          sub="At $1.99 per GPU hour"
        />
      </div>

      {USE_MOCKS && (
        <p className="text-sm text-muted">
          Numbers marked &ldquo;Not measured yet&rdquo; will be filled in by the benchmark run on the MI300X.
        </p>
      )}

      <div className="grid gap-5 lg:grid-cols-[2fr_1fr]">
        <Panel title="How it works">
          <ol className="space-y-5">
            {STEPS.map((s, i) => (
              <li key={s.title} className="flex gap-4">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-accent text-sm font-bold text-on-accent">
                  {i + 1}
                </span>
                <div>
                  <p className="font-semibold">{s.title}</p>
                  <p className="text-muted">{s.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </Panel>

        <div className="space-y-5">
          <Panel title="Where it runs" icon={<ChipIcon />}>
            <dl className="space-y-3">
              <div>
                <dt className="text-sm text-muted">GPU</dt>
                <dd className="font-semibold">{m?.gpu ?? "AMD Instinct MI300X"}</dd>
              </div>
              <div>
                <dt className="text-sm text-muted">Model</dt>
                <dd className="font-semibold">{m?.model ?? "Qwen2.5-VL-7B-Instruct"}</dd>
              </div>
              <div>
                <dt className="text-sm text-muted">Serving</dt>
                <dd className="font-semibold">vLLM on ROCm, AMD Developer Cloud</dd>
              </div>
            </dl>
          </Panel>
          <Panel title="Data sources">
            <ul className="list-disc space-y-1.5 pl-5 text-muted">
              {SOURCES.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
            <p className="mt-3 text-sm text-muted">All public US Government records.</p>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  sub,
  loading,
}: {
  label: string;
  value: string | null | undefined;
  sub?: string;
  loading: boolean;
}) {
  return (
    <div className="rounded-xl border border-line bg-surface p-5">
      <p className="text-sm font-medium text-muted">{label}</p>
      {loading ? (
        <Skeleton className="mt-2 h-10 w-28" />
      ) : value ? (
        <p className="tabular mt-1 text-4xl font-bold">{value}</p>
      ) : (
        <p className="mt-2 text-lg font-medium text-muted">Not measured yet</p>
      )}
      {sub && !loading && value && <p className="mt-1 text-sm text-muted">{sub}</p>}
    </div>
  );
}
