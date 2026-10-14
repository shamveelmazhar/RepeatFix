// Mock backend used when NEXT_PUBLIC_USE_MOCKS=true (or no API URL is set).
// It reads the fixtures in /mocks and answers with the same shapes as docs/API.md,
// so the UI can be built and demoed before the real backend is ready.

import cardsJson from "@/mocks/cards.json";
import knowledgeJson from "@/mocks/knowledge.json";
import metricsJson from "@/mocks/metrics.json";
import { ataName } from "./ata";
import type {
  AssistResponse,
  FailureMode,
  GroupBy,
  JobCard,
  Metrics,
  Procedure,
  RepeatRow,
  WorkOrder,
} from "./types";

const cards = (cardsJson as JobCard[]).map((c) => ({ ...c, ata_name: ataName(c.ata_chapter) }));

interface KnowledgeMode extends FailureMode {
  keywords: string[];
  hypotheses: { cause: string; confidence: "high" | "medium" | "low"; evidence_keywords: string[] }[];
  steps: string[];
  procedures: Procedure[];
}
const knowledge = knowledgeJson as unknown as {
  failure_modes: KnowledgeMode[];
  default_procedures: Procedure[];
};

const approved = new Set<string>();

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

function days(a: string, b: string) {
  return (new Date(b).getTime() - new Date(a).getTime()) / 86_400_000;
}

function tokens(text: string) {
  return text.toLowerCase().split(/[^a-z0-9#/]+/).filter((t) => t.length > 1);
}

export function computeRepeats(all: JobCard[], groupBy: GroupBy, minCount = 2): RepeatRow[] {
  const groups = new Map<string, JobCard[]>();
  for (const c of all) {
    const asset = groupBy === "aircraft" ? c.registration ?? `${c.aircraft_type} fleet` : c.component;
    const key = `${asset}|${c.failure_mode}`;
    groups.set(key, [...(groups.get(key) ?? []), c]);
  }
  const rows: RepeatRow[] = [];
  for (const [key, group] of groups) {
    if (group.length < minCount) continue;
    const dated = group.filter((c) => c.date).sort((a, b) => a.date!.localeCompare(b.date!));
    const span = dated.length > 1 ? days(dated[0].date!, dated[dated.length - 1].date!) : null;
    rows.push({
      asset: key.split("|")[0],
      aircraft_type: group[0].aircraft_type,
      ata_chapter: group[0].ata_chapter,
      ata_name: ataName(group[0].ata_chapter),
      failure_mode: group[0].failure_mode,
      count: group.length,
      mtbf_days: span !== null ? Math.round((span / (dated.length - 1)) * 10) / 10 : null,
      downtime_hours: group.reduce((s, c) => s + (c.downtime_hours ?? 0), 0),
      card_ids: dated.map((c) => c.id),
    });
  }
  return rows.sort((a, b) => b.downtime_hours - a.downtime_hours || b.count - a.count);
}

function pickMode(text: string): KnowledgeMode | undefined {
  const t = text.toLowerCase();
  let best: KnowledgeMode | undefined;
  let bestHits = 0;
  for (const m of knowledge.failure_modes) {
    const hits = m.keywords.filter((k) => t.includes(k)).length;
    if (hits > bestHits) {
      best = m;
      bestHits = hits;
    }
  }
  return best;
}

export const mockApi = {
  async getCards(): Promise<JobCard[]> {
    await delay(150);
    return cards;
  },

  async getCard(id: string): Promise<JobCard | undefined> {
    return cards.find((c) => c.id === id);
  },

  async getRepeats(groupBy: GroupBy): Promise<RepeatRow[]> {
    await delay(250);
    return computeRepeats(cards, groupBy);
  },

  async getFailureModes(): Promise<FailureMode[]> {
    return knowledge.failure_modes.map(({ code, label, ata_chapter }) => ({ code, label, ata_chapter }));
  },

  async getMetrics(): Promise<Metrics> {
    await delay(150);
    return { ...(metricsJson as Metrics), repeat_groups_found: computeRepeats(cards, "aircraft").length };
  },

  async ingestImage(): Promise<JobCard> {
    await delay(1200);
    return {
      id: "photo-0001",
      source: "photo",
      date: null,
      aircraft_type: "B737-800",
      registration: "N804RF",
      ata_chapter: "32",
      ata_name: ataName("32"),
      component: "#2 main gear brake",
      symptom: "Brake temp high after landing, brake feels slow to release",
      failure_mode: "brake_overheat",
      action_taken: "",
      parts: [],
      downtime_hours: null,
      raw_text: "#2 BRK TEMP HI AFTER LDG. BRK SLOW TO RELEASE. PLS CK.",
    };
  },

  async assist(faultText: string, asset: string | null): Promise<AssistResponse> {
    const started = performance.now();
    await delay(900);
    const mode = pickMode(faultText);
    const words = new Set(tokens(faultText));

    const scored = cards
      .map((c) => {
        const overlap = tokens(`${c.symptom} ${c.component} ${c.raw_text}`).filter((t) => words.has(t)).length;
        let score = overlap / Math.max(words.size, 1);
        if (mode && c.failure_mode === mode.code) score += 0.5;
        if (asset && c.registration === asset) score += 0.2;
        return { card: c, score: Math.min(0.97, Math.round(score * 100) / 100) };
      })
      .filter((s) => s.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 3);

    const top = scored[0]?.card;
    const chapter = mode?.ata_chapter ?? top?.ata_chapter ?? "05";
    const assetCard = asset ? cards.find((c) => c.registration === asset) : undefined;
    const aircraftType = assetCard?.aircraft_type ?? top?.aircraft_type ?? "Unknown";

    const history = cards
      .filter((c) => mode && c.failure_mode === mode.code && (asset ? c.registration === asset : true))
      .sort((a, b) => (a.date ?? "").localeCompare(b.date ?? ""));
    const modeCards = cards.filter((c) => mode && c.failure_mode === mode.code);

    const hypotheses = (mode?.hypotheses ?? []).map((h) => ({
      cause: h.cause,
      confidence: h.confidence,
      evidence_card_ids: modeCards
        .filter((c) => h.evidence_keywords.some((k) => `${c.raw_text} ${c.action_taken}`.toLowerCase().includes(k)))
        .map((c) => c.id),
    }));

    const workOrder: WorkOrder = {
      title: `Troubleshoot: ${mode?.label ?? "reported fault"}${asset ? ` — ${asset}` : ""}`,
      asset,
      steps: mode?.steps ?? ["Inspect the reported area.", "Record findings.", "Rectify and perform ops check."],
      parts: Array.from(new Set(scored.flatMap((s) => s.card.parts))).slice(0, 3),
      est_hours: top?.downtime_hours ?? null,
      status: "draft",
    };

    return {
      id: `wo-${Date.now().toString(36)}`,
      structured: {
        id: "new",
        source: "text",
        date: new Date().toISOString().slice(0, 10),
        aircraft_type: aircraftType,
        registration: asset,
        ata_chapter: chapter,
        ata_name: ataName(chapter),
        component: top?.component ?? "Not identified",
        symptom: faultText.trim(),
        failure_mode: mode?.code ?? "unclassified",
        action_taken: "",
        parts: [],
        downtime_hours: null,
        raw_text: faultText,
      },
      similar: scored,
      hypotheses,
      procedures: mode?.procedures ?? knowledge.default_procedures,
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
      timing: { total_ms: Math.round(performance.now() - started), tokens_per_s: null },
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
