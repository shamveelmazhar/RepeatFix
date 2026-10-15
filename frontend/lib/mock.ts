// Cached demo backend, used when NEXT_PUBLIC_USE_MOCKS=true (or no API URL is set).
// It answers with the same shapes as docs/API.md from the fixtures in /mocks, which hold
// real records: FAA SDR job cards for 40 tails, NASA ASRS reports, and cited sections of
// AC 43.13-1B and the AMT Handbooks. Rebuild them with scripts/build_mock_fixtures.py.
// No model runs here: matching is word overlap and every number is counted from the cards.

import knowledgeJson from "@/mocks/knowledge.json";
import metricsJson from "@/mocks/metrics.json";
import { ataName } from "./ata";
import type {
  AssistResponse,
  FailureMode,
  GroupBy,
  Hypothesis,
  JobCard,
  Metrics,
  Procedure,
  RepeatRow,
  WorkOrder,
} from "./types";

const knowledge = knowledgeJson as unknown as {
  failure_modes: FailureMode[];
  procedures: Record<string, Procedure[]>;
  default_procedures: Procedure[];
};

// The card set is large, so it loads in its own chunk on first use.
let cardsPromise: Promise<JobCard[]> | null = null;
function loadCards(): Promise<JobCard[]> {
  cardsPromise ??= import("@/mocks/cards.json").then((m) =>
    (m.default as unknown as JobCard[]).map((c) => ({ ...c, ata_name: c.ata_name ?? ataName(c.ata_chapter) })),
  );
  return cardsPromise;
}

const approved = new Set<string>();

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Same rule as the backend: reports of one group closer than this are one event, not a repeat. */
const MIN_GAP_DAYS = 7;

function days(a: string, b: string) {
  return (new Date(b).getTime() - new Date(a).getTime()) / 86_400_000;
}

const groupKey = (c: JobCard) => `${c.ata_chapter}|${c.failure_mode}`;

/** Dated cards of one group, oldest first, keeping only reports at least MIN_GAP_DAYS after the last kept one (per tail). */
function spacedEvents(group: JobCard[]): JobCard[] {
  const dated = group.filter((c) => c.date).sort((a, b) => a.date!.localeCompare(b.date!));
  const last = new Map<string, string>();
  return dated.filter((c) => {
    const tail = c.registration ?? c.id;
    const prev = last.get(tail);
    if (prev && days(prev, c.date!) < MIN_GAP_DAYS) return false;
    last.set(tail, c.date!);
    return true;
  });
}

/** Repeat failures: same aircraft (or component) + ATA chapter + failure mode, at least 7 days apart. */
export function computeRepeats(all: JobCard[], groupBy: GroupBy, minCount = 2): RepeatRow[] {
  const groups = new Map<string, JobCard[]>();
  for (const c of all) {
    const asset = groupBy === "aircraft" ? c.registration : c.component;
    if (!asset) continue;
    const key = `${asset}|${groupKey(c)}`;
    groups.set(key, [...(groups.get(key) ?? []), c]);
  }
  const rows: RepeatRow[] = [];
  for (const [key, group] of groups) {
    const events = spacedEvents(group);
    if (events.length < minCount) continue;
    const span = days(events[0].date!, events[events.length - 1].date!);
    rows.push({
      asset: key.split("|")[0],
      aircraft_type: group[group.length - 1].aircraft_type,
      ata_chapter: group[0].ata_chapter,
      ata_name: group[0].ata_name,
      failure_mode: group[0].failure_mode,
      count: events.length,
      mtbf_days: Math.round((span / (events.length - 1)) * 10) / 10,
      downtime_hours: group.reduce((s, c) => s + (c.downtime_hours ?? 0), 0),
      card_ids: group
        .filter((c) => c.date)
        .sort((a, b) => a.date!.localeCompare(b.date!))
        .map((c) => c.id),
    });
  }
  return rows.sort((a, b) => b.downtime_hours - a.downtime_hours || b.count - a.count);
}

// ---------------------------------------------------------------- matching

const STOP = new Set(
  "the and for with was were has had are from this that not but per iaw ref see on in at of to a an is it by as or no ops chk check good found reported rpt".split(
    " ",
  ),
);

function tokens(text: string) {
  return text
    .toLowerCase()
    .split(/[^a-z0-9#]+/)
    .filter((t) => t.length > 1 && !STOP.has(t));
}

let idfCache: Map<string, number> | null = null;
function idf(cards: JobCard[]): Map<string, number> {
  if (idfCache) return idfCache;
  const df = new Map<string, number>();
  for (const c of cards) for (const t of new Set(tokens(`${c.symptom} ${c.component}`))) df.set(t, (df.get(t) ?? 0) + 1);
  idfCache = new Map([...df].map(([t, f]) => [t, Math.log(1 + cards.length / f)]));
  return idfCache;
}

/** Share of the fault's (rarity-weighted) words that also appear in the card. */
function overlapScore(query: string[], card: JobCard, weights: Map<string, number>, maxIdf: number) {
  const words = new Set(tokens(`${card.symptom} ${card.component}`));
  let hit = 0;
  let total = 0;
  for (const t of query) {
    const w = weights.get(t) ?? maxIdf;
    total += w;
    if (words.has(t)) hit += w;
  }
  return total ? hit / total : 0;
}

/** Likely causes: the components named most often in past reports of this problem. */
function likelyCauses(group: JobCard[], scope: string): Hypothesis[] {
  const byComponent = new Map<string, JobCard[]>();
  for (const c of group) {
    if (!c.component || c.component === c.ata_name) continue; // only the chapter name, no part named
    const k = c.component.toLowerCase();
    byComponent.set(k, [...(byComponent.get(k) ?? []), c]);
  }
  return [...byComponent.values()]
    .sort((a, b) => b.length - a.length)
    .filter((cs, i) => i === 0 || cs.length >= 2) // a part named once is not a pattern
    .slice(0, 3)
    .map((cs) => {
      const share = cs.length / group.length;
      const newest = [...cs].sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""));
      return {
        cause: `${cs[0].component}: named in ${cs.length} of ${group.length} past reports of this problem ${scope}`,
        confidence: share >= 0.4 ? "high" : share >= 0.15 ? "medium" : "low",
        evidence_card_ids: [...newest.filter((c) => c.action_taken), ...newest.filter((c) => !c.action_taken)]
          .slice(0, 4)
          .map((c) => c.id),
      };
    });
}

export const mockApi = {
  async getCards(): Promise<JobCard[]> {
    return loadCards();
  },

  async getCard(id: string): Promise<JobCard | undefined> {
    return (await loadCards()).find((c) => c.id === id);
  },

  async getRepeats(groupBy: GroupBy): Promise<RepeatRow[]> {
    return computeRepeats(await loadCards(), groupBy);
  },

  async getFailureModes(): Promise<FailureMode[]> {
    return knowledge.failure_modes;
  },

  async getMetrics(): Promise<Metrics> {
    return metricsJson as Metrics;
  },

  /** No model runs in the cached demo, so a "photo" returns a real logged entry: the latest N926NK fume event. */
  async ingestImage(): Promise<JobCard> {
    await delay(800);
    const cards = await loadCards();
    const example = cards
      .filter((c) => c.registration === "N926NK" && c.ata_chapter === "21" && c.failure_mode === "smoke_or_odor")
      .sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""))[0];
    return { ...example, id: "photo-0001", source: "photo", action_taken: "", parts: [], raw_text: example.symptom };
  },

  /** `asset` narrows to one tail; `aircraftType` (when no tail is picked) narrows to that type's fleet. */
  async assist(faultText: string, asset: string | null, aircraftType: string | null = null): Promise<AssistResponse> {
    const started = performance.now();
    const cards = await loadCards();
    const weights = idf(cards);
    const maxIdf = Math.max(...weights.values());
    const query = [...new Set(tokens(faultText))];

    // 1. Closest past cards by wording.
    const base = cards
      .map((card) => ({ card, score: overlapScore(query, card, weights, maxIdf) }))
      .filter((s) => s.score > 0)
      .sort((a, b) => b.score - a.score);

    // 2. Read the fault as the ATA chapter + failure mode most of the close matches share.
    const votes = new Map<string, number>();
    for (const s of base.slice(0, 10)) votes.set(groupKey(s.card), (votes.get(groupKey(s.card)) ?? 0) + s.score);
    const key = [...votes].sort((a, b) => b[1] - a[1])[0]?.[0];
    const [chapter, mode] = key ? key.split("|") : ["05", "other"];

    // 3. Re-rank: same problem and same aircraft count for more than wording alone.
    const scored = base
      .slice(0, 50)
      .map(({ card, score }) => {
        let s = score;
        if (groupKey(card) === key) s += 0.25;
        if (asset && card.registration === asset) s += 0.15;
        else if (aircraftType && card.aircraft_type === aircraftType) s += 0.1;
        return { card, score: s };
      })
      .sort((a, b) => b.score - a.score || (b.card.date ?? "").localeCompare(a.card.date ?? ""))
      .slice(0, 3)
      .map(({ card, score }) => ({ card, score: Math.min(0.97, Math.round(score * 100) / 100) }));

    const top = scored[0]?.card;
    const scopeCards = asset
      ? cards.filter((c) => c.registration === asset)
      : aircraftType
        ? cards.filter((c) => c.aircraft_type === aircraftType)
        : [];
    const scopeName = asset ? `on ${asset}` : aircraftType ? `on ${aircraftType} aircraft` : "across the fleet";
    const readType = asset ? (scopeCards[0]?.aircraft_type ?? aircraftType) : aircraftType;
    const fleetGroup = cards.filter((c) => groupKey(c) === key);
    const scopeGroup = scopeCards.filter((c) => groupKey(c) === key);
    const scoped = asset !== null || aircraftType !== null;
    const useScope = scoped && scopeGroup.length >= 3;
    const causeGroup = useScope ? scopeGroup : fleetGroup;

    const hypotheses = likelyCauses(causeGroup, useScope ? scopeName : "across the fleet");
    const procedures = (key && knowledge.procedures[key]) || knowledge.default_procedures;
    const history = spacedEvents(scoped ? scopeGroup : fleetGroup);
    const label = failureModeLabel(mode);

    const steps = [
      ...hypotheses.slice(0, 2).map((h) => `Inspect the ${h.cause.split(":")[0].toLowerCase()} (most often named in past reports).`),
      ...procedures.slice(0, 1).map((p) => `Follow ${p.citation ?? `${p.doc}, ${p.section}`} and the aircraft maintenance manual.`),
      ...(history.length >= 2
        ? [`Repeat problem (logged ${history.length} times since ${history[0].date}): review the past fixes before replacing the same part again.`]
        : []),
      "Record findings, do an operational check and close out the log entry.",
    ];

    const workOrder: WorkOrder = {
      title: `Troubleshoot: ${label}${asset || aircraftType ? ` — ${asset ?? aircraftType}` : ""}`,
      asset,
      steps,
      parts: Array.from(new Set(scored.flatMap((s) => s.card.parts))).slice(0, 3),
      est_hours: null, // FAA SDR records no downtime, so there is nothing to estimate from
      status: "draft",
    };

    const totalMs = Math.round(performance.now() - started);
    await delay(600);

    return {
      id: `wo-${Date.now().toString(36)}`,
      structured: {
        id: "new",
        source: "text",
        date: new Date().toISOString().slice(0, 10),
        aircraft_type: readType ?? top?.aircraft_type ?? "Unknown",
        registration: asset,
        ata_chapter: chapter,
        ata_name: ataName(chapter),
        component: top && groupKey(top) === key ? top.component : "Not identified",
        symptom: faultText.trim(),
        failure_mode: mode,
        action_taken: "",
        parts: [],
        downtime_hours: null,
        raw_text: faultText,
      },
      similar: scored,
      hypotheses,
      procedures,
      work_order: workOrder,
      repeat_history:
        history.length > 0
          ? {
              count: history.length,
              first_date: history[0].date,
              last_date: history[history.length - 1].date,
              card_ids: history.map((c) => c.id),
            }
          : null,
      timing: { total_ms: totalMs, tokens_per_s: null },
    };
  },

  async approve(id: string): Promise<{ id: string; status: "approved" }> {
    await delay(400);
    approved.add(id);
    return { id, status: "approved" };
  },
};

export function failureModeLabel(code: string): string {
  return (
    knowledge.failure_modes.find((m) => m.code === code)?.label ??
    code.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase())
  );
}
