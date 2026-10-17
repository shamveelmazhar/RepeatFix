"use client";

import { useEffect, useState } from "react";
import { BoltIcon, ChipIcon, ClockIcon, CoinIcon, FileIcon, RepeatIcon, TargetIcon } from "@/components/icons";
import { Panel, StatTile } from "@/components/ui";
import { api } from "@/lib/api";
import { DEFAULT_GPU, servingLabel, shortModel } from "@/lib/runtime";
import type { Metrics } from "@/lib/types";
import insights from "@/mocks/insights.json";
import fullSet from "@/mocks/metrics.json";

// Measured on the full FAA SDR build by scripts/build_insights.py, so it shows in every mode.
const NOT_STICK = insights.fix_did_not_stick;
// The live backend only loads the 40-aircraft demo slice, so the full-set counts come from the build too.
const FULL_CARDS = fullSet.cards_processed;
const FULL_REPEATS = fullSet.repeat_groups_found;

const STEPS = [
  {
    title: "Read the logs",
    body: "Messy write-ups and abbreviations are turned into clean job cards: aircraft, ATA chapter, component, symptom, fix and parts.",
  },
  {
    title: "Find the repeats",
    body: "Job cards are grouped by aircraft and problem. Counts and days between failures are plain arithmetic, so every number can be checked.",
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
  "FAA Service Difficulty Reports, Jan 2024 to Oct 2026 (malfunction and defect reports)",
  "NASA ASRS maintenance reports, 2022 to 2024",
  "FAA AC 43.13-1B CHG 1: Acceptable Methods, Techniques, and Practices",
  "FAA Aviation Maintenance Technician Handbooks: General, Airframe, Powerplant",
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
          Measured numbers, not claims: what RepeatFix found in real FAA records, and how it runs.
        </p>
      </header>

      {error && (
        <p role="alert" className="rounded-xl border border-critical/30 bg-critical-soft p-4 text-critical">
          {error}
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatTile tint="peach" icon={<RepeatIcon />}
          label="Fixes that didn't stick"
          value={NOT_STICK.share === null ? null : `${Math.round(NOT_STICK.share * 100)}%`}
          sub={`${NOT_STICK.came_back.toLocaleString()} of ${NOT_STICK.fixes.toLocaleString()} recorded fixes: the same problem came back on the same aircraft within ${NOT_STICK.window_days} days`}
        />
        <StatTile tint="sand" icon={<FileIcon />}
          label="Job cards processed"
          value={FULL_CARDS.toLocaleString()}
          sub="FAA SDR reports 2024 to 2026 and NASA ASRS reports"
        />
        <StatTile tint="slate" icon={<RepeatIcon />}
          label="Repeat problems found"
          value={FULL_REPEATS.toLocaleString()}
          sub={`In all ${FULL_CARDS.toLocaleString()} reports: same aircraft, ATA chapter and problem, 7+ days apart`}
        />
        {/* Model numbers show once the benchmark on AMD Token Factory has measured them. */}
        {m?.extraction_field_accuracy != null && (
          <StatTile tint="peach" icon={<TargetIcon />}
            label="Agreement with parser"
            value={pct(m.extraction_field_accuracy)}
            sub={`Model vs our rule-based parser's labels, on ${m.labelled_cards} job cards`}
          />
        )}
        {m?.p50_latency_ms != null && (
          <StatTile tint="sand" icon={<ClockIcon />}
            label="Time to answer a fault"
            value={`${(m.p50_latency_ms / 1000).toFixed(1)} s`}
            sub="Typical (median) time"
          />
        )}
        {m?.tokens_per_s != null && (
          <StatTile tint="slate" icon={<BoltIcon />} label="Generation speed" value={`${Math.round(m.tokens_per_s)} tokens/s`} />
        )}
        {m?.cost_per_100_cards_usd != null && (
          <StatTile tint="peach" icon={<CoinIcon />}
            label="Cost per 100 job cards"
            value={`$${m.cost_per_100_cards_usd.toFixed(2)}`}
          />
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-[2fr_1fr]">
        <Panel title="How it works">
          <ol className="space-y-5">
            {STEPS.map((s, i) => (
              <li key={s.title} className="flex gap-4">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-accent-gradient text-sm font-bold text-on-accent">
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
                <dd className="font-semibold">{m?.gpu || DEFAULT_GPU}</dd>
              </div>
              <div>
                <dt className="text-sm text-muted">Model</dt>
                <dd className="font-semibold">{shortModel(m?.model ?? null) ?? "Not measured yet"}</dd>
              </div>
              <div>
                <dt className="text-sm text-muted">Serving</dt>
                <dd className="font-semibold">{servingLabel(m?.gpu || DEFAULT_GPU)}</dd>
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
