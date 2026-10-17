"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { CardLink, useOpenCard } from "@/components/CardViewer";
import { AlertIcon, BookIcon, CameraIcon, CheckIcon, HistoryIcon, SearchIcon } from "@/components/icons";
import { AtaTag, Button, Panel, Skeleton, StatusBadge, formatDate } from "@/components/ui";
import { type AssistResult, USE_MOCKS, api } from "@/lib/api";
import { useRuntime } from "@/lib/runtime";
import { failureModeLabel } from "@/lib/mock";
import type { JobCard, WorkOrder } from "@/lib/types";

// Real write-ups from the FAA SDR records: N926NK fume events, N2193J fire loop faults, N3760C exit lights.
// Picking one also picks its aircraft, so the repeat alert counts that tail's history.
const EXAMPLES = [
  { text: "FUME EVENT ON DESCENT IN COCKPIT", tail: "N926NK" },
  { text: "ENG 2 FIRE LOOP B FAULT", tail: "N2193J" },
  { text: "FOUND FWD LH EMERG EXIT LIGHTS INOP", tail: "N3760C" },
];

export default function FixAFaultPage() {
  const [fleet, setFleet] = useState<{ tail: string; type: string }[]>([]);
  const [aircraftType, setAircraftType] = useState("");
  const [asset, setAsset] = useState("");
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [reading, setReading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorTitle, setErrorTitle] = useState("Couldn't get an answer");
  const [result, setResult] = useState<AssistResult | null>(null);
  const [askedType, setAskedType] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .getCards()
      .then((cards) => {
        const typeOf = new Map<string, string>();
        for (const c of cards) if (c.registration) typeOf.set(c.registration, c.aircraft_type);
        setFleet([...typeOf].map(([tail, type]) => ({ tail, type })).sort((a, b) => a.tail.localeCompare(b.tail)));
      })
      .catch(() => setFleet([]));
  }, []);

  const types = Array.from(new Set(fleet.map((a) => a.type))).sort();
  const tails = fleet.filter((a) => !aircraftType || a.type === aircraftType);

  function pickTail(tail: string) {
    setAsset(tail);
    const type = fleet.find((a) => a.tail === tail)?.type;
    if (type) setAircraftType(type);
  }

  function pickType(type: string) {
    setAircraftType(type);
    if (asset && fleet.find((a) => a.tail === asset)?.type !== type) setAsset("");
  }

  async function submit(e?: React.FormEvent) {
    e?.preventDefault();
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setErrorTitle("Couldn't get an answer");
    setResult(null);
    try {
      setResult(await api.assist(text, asset || null, aircraftType || null));
      setAskedType(aircraftType || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function readPhoto(file: File | undefined) {
    if (!file) return;
    setReading(true);
    setError(null);
    setErrorTitle("Couldn't read the photo");
    try {
      const card = await api.ingestImage(file);
      setText(card.raw_text || card.symptom);
      if (card.registration) pickTail(card.registration);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read the photo.");
    } finally {
      setReading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  function reset() {
    setResult(null);
    setText("");
    setAsset("");
    setAircraftType("");
  }

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Fix a fault</h1>
        <p className="mt-2 max-w-2xl text-lg text-muted">
          Describe the problem. RepeatFix shows how it was fixed before, the likely causes and the procedure to
          follow.
        </p>
      </header>

      <Panel>
        <form onSubmit={submit} className="space-y-5">
          <div className="grid gap-5 sm:grid-cols-[220px_1fr]">
            <div className="space-y-4">
              <div>
                <label htmlFor="aircraft-type" className="mb-1.5 block font-medium">
                  Aircraft type
                </label>
                <select
                  id="aircraft-type"
                  value={aircraftType}
                  onChange={(e) => pickType(e.target.value)}
                  className="min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-ink focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent/15"
                >
                  <option value="">Any type</option>
                  {types.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="asset" className="mb-1.5 block font-medium">
                  Tail number
                </label>
                <select
                  id="asset"
                  value={asset}
                  onChange={(e) => pickTail(e.target.value)}
                  className="min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-ink focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent/15"
                >
                  <option value="">{aircraftType ? `Any ${aircraftType}` : "Not sure / any"}</option>
                  {tails.map((a) => (
                    <option key={a.tail} value={a.tail}>
                      {a.tail}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label htmlFor="fault" className="mb-1.5 block font-medium">
                What&apos;s the problem?
              </label>
              <textarea
                id="fault"
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={5}
                placeholder="Type it the way you would write it in the logbook"
                className="w-full rounded-xl border border-line bg-surface px-3 py-2.5 text-ink placeholder:text-muted focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent/15"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted">Try:</span>
            {EXAMPLES.map((ex) => (
              <button
                key={ex.text}
                type="button"
                onClick={() => {
                  setText(ex.text);
                  pickTail(ex.tail);
                }}
                className="glass-inset rounded-full px-3 py-1 text-sm text-muted transition-colors hover:border-accent hover:text-accent"
              >
                {ex.text}
              </button>
            ))}
          </div>

          <div className="flex flex-col-reverse gap-3 border-t border-line pt-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                capture="environment"
                className="hidden"
                onChange={(e) => readPhoto(e.target.files?.[0])}
              />
              <Button type="button" variant="secondary" onClick={() => fileRef.current?.click()} disabled={reading}>
                <CameraIcon />
                {reading ? "Reading photo…" : "Read a photo of a log entry"}
                <span className="rounded bg-accent-soft px-1.5 text-xs font-semibold text-accent">Beta</span>
              </Button>
            </div>
            <Button type="submit" disabled={loading || !text.trim()} className="px-6 text-lg">
              <SearchIcon />
              {loading ? "Searching past fixes…" : "Find past fixes"}
            </Button>
          </div>
        </form>
      </Panel>

      {error && (
        <div role="alert" className="flex items-start gap-3 rounded-xl border border-critical/30 bg-critical-soft p-4 text-critical">
          <AlertIcon className="mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">{errorTitle}</p>
            <p>{error}</p>
          </div>
        </div>
      )}

      {loading && <LoadingResults />}
      {result && <Results result={result} fleetType={askedType} onReset={reset} />}
    </div>
  );
}

function LoadingResults() {
  return (
    <div className="grid gap-6 lg:grid-cols-3" aria-busy="true" aria-label="Loading results">
      {[0, 1, 2].map((i) => (
        <div key={i} className="glass space-y-3 rounded-2xl p-6">
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
      ))}
    </div>
  );
}

function matchLabel(score: number) {
  if (score >= 0.75) return "Close match";
  if (score >= 0.5) return "Good match";
  return "Partial match";
}

const CONFIDENCE_LABEL = { high: "Most likely", medium: "Possible", low: "Less likely" } as const;

function Results({
  result,
  fleetType,
  onReset,
}: {
  result: AssistResult;
  /** The aircraft type the search was narrowed to, if any. */
  fleetType: string | null;
  onReset: () => void;
}) {
  const openCard = useOpenCard();
  const s = result.structured;
  const history = result.repeat_history;
  const { gpu } = useRuntime();
  // A live backend answered from its saved answers, or couldn't answer and we used the saved demo.
  const savedNote = USE_MOCKS
    ? null
    : result.savedDemo
      ? "The live model is busy or can't be reached, so this answer comes from the saved demo. Try again in a minute for a live answer."
      : result.cached_for
        ? `The live model is busy, so this is the saved answer for a similar fault: “${result.cached_for}”. Try again in a minute for a live answer.`
        : result.cached
          ? "This fault was answered before, so this is the saved answer from that live run."
          : null;

  return (
    <div className="space-y-6">
      {savedNote && (
        <div
          role="status"
          className="flex flex-col gap-2 rounded-2xl border border-warning/30 bg-warning-soft p-4 text-warning sm:flex-row sm:items-center sm:gap-3"
        >
          <StatusBadge severity="warning">Saved answer</StatusBadge>
          <p className="text-sm">{savedNote}</p>
        </div>
      )}
      {history && history.count >= 2 && (
        <div
          role="status"
          className={`flex flex-col gap-3 rounded-2xl border p-5 shadow-sm sm:flex-row sm:items-center sm:justify-between ${
            history.count >= 3
              ? "border-critical/30 bg-critical-soft text-critical"
              : "border-warning/30 bg-warning-soft text-warning"
          }`}
        >
          <div className="flex items-start gap-3">
            <AlertIcon className="mt-0.5 shrink-0" />
            <div>
              <p className="text-lg font-semibold">
                Repeat failure: logged {history.count} times before
                {s.registration ? ` on ${s.registration}` : fleetType ? ` across the ${fleetType} fleet` : " across the fleet"}
              </p>
              <p className="text-ink">
                {failureModeLabel(s.failure_mode)}, {formatDate(history.first_date)} to {formatDate(history.last_date)}.
                Replacing the same part again may not stop it. Check the likely causes below.
              </p>
            </div>
          </div>
          <Link href="/repeats" className="shrink-0 font-semibold underline underline-offset-4">
            See repeat failures
          </Link>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 text-muted">
        <span className="eyebrow">Read as</span>
        <AtaTag chapter={s.ata_chapter} name={s.ata_name} />
        <span className="rounded-md border border-line px-2 py-0.5 text-sm text-ink">{failureModeLabel(s.failure_mode)}</span>
        <span className="text-sm">
          {s.registration ?? (fleetType ? "Any tail" : "Any aircraft")} · {s.aircraft_type}
        </span>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Panel title="Seen before" icon={<HistoryIcon />} lift>
          {result.similar.length === 0 ? (
            <p className="text-muted">No similar past fixes found.</p>
          ) : (
            <ul className="space-y-3">
              {withFixFirst(result.similar).map(({ card, score }) => (
                <li key={card.id}>
                  <button
                    onClick={() => openCard(card.id)}
                    className="w-full glass-inset rounded-xl p-3 text-left transition-colors hover:border-accent"
                  >
                    <span className="mb-1.5 inline-block rounded-full bg-accent-soft px-2 py-0.5 text-xs font-semibold text-accent">
                      {matchLabel(score)}
                    </span>
                    <p className="line-clamp-3 font-medium">{card.symptom}</p>
                    <p className="text-sm text-muted">
                      {card.registration ?? card.aircraft_type} · {formatDate(card.date)}
                    </p>
                    <p className="mt-1 line-clamp-3 text-sm text-muted">
                      <span className="font-medium text-ink">Fix:</span> {card.action_taken || "Not recorded"}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Likely causes" icon={<SearchIcon />} lift>
          {result.hypotheses.length === 0 ? (
            <p className="text-muted">Not enough past records to suggest a cause.</p>
          ) : (
            <ol className="space-y-4">
              {result.hypotheses.map((h, i) => (
                <li key={h.cause} className="flex gap-3">
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-accent/30 bg-accent-soft text-sm font-bold text-accent">
                    {i + 1}
                  </span>
                  <div>
                    <p className="eyebrow">{CONFIDENCE_LABEL[h.confidence]}</p>
                    <p className="font-medium">{h.cause}</p>
                    {h.evidence_card_ids.length > 0 ? (
                      <p className="mt-1 flex flex-wrap gap-1.5 text-sm text-muted">
                        Based on:
                        {h.evidence_card_ids.map((id) => (
                          <CardLink key={id} id={id} className="font-medium text-accent underline underline-offset-2" />
                        ))}
                      </p>
                    ) : (
                      <p className="mt-1 text-sm text-muted">No past record supports this yet.</p>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Panel>

        <Panel title="Procedure" icon={<BookIcon />} lift>
          {result.procedures.length === 0 ? (
            <p className="text-muted">
              No matching procedure found in AC 43.13-1B or the FAA handbooks. Check the aircraft maintenance manual.
            </p>
          ) : (
            <ul className="space-y-3">
              {result.procedures.map((p) => (
                <li key={`${p.doc}-${p.section}`} className="glass-inset rounded-xl p-3">
                  <p className="text-sm font-semibold text-muted">{p.doc}</p>
                  <p className="font-medium">
                    {p.section}
                    {(p.page_label ?? p.page) != null && (
                      <span className="text-muted">, page {p.page_label ?? p.page}</span>
                    )}
                  </p>
                  <p className="mt-1 text-sm text-muted">{p.snippet}</p>
                  {p.url && (
                    <a href={p.url} target="_blank" rel="noreferrer" className="mt-1 inline-block text-sm font-medium text-accent underline">
                      Open document
                    </a>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <WorkOrderPanel key={result.id} id={result.id} initial={result.work_order} onReset={onReset} />

      <p className="text-sm text-muted">
        {USE_MOCKS || result.savedDemo ? (
          "Saved demo: matched by wording against real FAA records, without the model."
        ) : result.cached ? (
          `Saved answer from an earlier live run on ${gpu}.`
        ) : (
          <>
            Answered in {(result.timing.total_ms / 1000).toFixed(1)} s
            {result.timing.tokens_per_s ? ` · ${Math.round(result.timing.tokens_per_s)} tokens/s` : ""} · on {gpu}
          </>
        )}
      </p>
    </div>
  );
}

function WorkOrderPanel({ id, initial, onReset }: { id: string; initial: WorkOrder; onReset: () => void }) {
  const [title, setTitle] = useState(initial.title);
  const [steps, setSteps] = useState(initial.steps.join("\n"));
  const [parts, setParts] = useState(initial.parts.join(", "));
  const [hours, setHours] = useState(initial.est_hours?.toString() ?? "");
  const [approver, setApprover] = useState("");
  const [saving, setSaving] = useState(false);
  const [approved, setApproved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function approve() {
    setSaving(true);
    setError(null);
    const wo: WorkOrder = {
      title,
      asset: initial.asset,
      steps: steps.split("\n").map((s) => s.trim()).filter(Boolean),
      parts: parts.split(",").map((s) => s.trim()).filter(Boolean),
      est_hours: hours ? Number(hours) : null,
      status: "approved",
    };
    try {
      await api.approve(id, wo, approver.trim());
      setApproved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not approve.");
    } finally {
      setSaving(false);
    }
  }

  const input =
    "w-full rounded-xl border border-line bg-surface px-3 py-2 text-ink focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent/15 disabled:bg-bg disabled:text-muted";

  return (
    <Panel
      title="Draft work order"
      icon={<CheckIcon />}
      action={approved ? <StatusBadge severity="ok">Approved</StatusBadge> : <StatusBadge severity="neutral">Draft</StatusBadge>}
    >
      <div className="space-y-4">
        <div>
          <label htmlFor="wo-title" className="mb-1.5 block text-sm font-medium text-muted">
            Title
          </label>
          <input id="wo-title" value={title} onChange={(e) => setTitle(e.target.value)} disabled={approved} className={input} />
        </div>
        <div>
          <label htmlFor="wo-steps" className="mb-1.5 block text-sm font-medium text-muted">
            Steps (one per line)
          </label>
          <textarea
            id="wo-steps"
            value={steps}
            onChange={(e) => setSteps(e.target.value)}
            rows={Math.max(4, initial.steps.length + 1)}
            disabled={approved}
            className={input}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-[1fr_160px_1fr]">
          <div>
            <label htmlFor="wo-parts" className="mb-1.5 block text-sm font-medium text-muted">
              Parts that may be needed
            </label>
            <input id="wo-parts" value={parts} onChange={(e) => setParts(e.target.value)} disabled={approved} className={input} />
          </div>
          <div>
            <label htmlFor="wo-hours" className="mb-1.5 block text-sm font-medium text-muted">
              Est. hours
            </label>
            <input
              id="wo-hours"
              type="number"
              min={0}
              step={0.5}
              value={hours}
              onChange={(e) => setHours(e.target.value)}
              disabled={approved}
              className={`${input} tabular`}
            />
          </div>
          <div>
            <label htmlFor="wo-approver" className="mb-1.5 block text-sm font-medium text-muted">
              Approved by
            </label>
            <input
              id="wo-approver"
              value={approver}
              onChange={(e) => setApprover(e.target.value)}
              placeholder="Supervisor name"
              disabled={approved}
              className={input}
            />
          </div>
        </div>

        {error && <p className="text-critical">{error}</p>}

        <div className="flex flex-col gap-3 border-t border-line pt-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted">
            {approved
              ? `Approved by ${approver}. The work order is ready to issue.`
              : "Nothing is issued until a supervisor reviews and approves this draft."}
          </p>
          {approved ? (
            <Button variant="secondary" onClick={onReset}>
              Start a new fault
            </Button>
          ) : (
            <Button onClick={approve} disabled={saving || !approver.trim()}>
              <CheckIcon />
              {saving ? "Approving…" : "Approve work order"}
            </Button>
          )}
        </div>
      </div>
    </Panel>
  );
}

/** Past cards that record what was done come first: the fix is what a technician is looking for. Order is kept otherwise. */
function withFixFirst<T extends { card: JobCard }>(similar: T[]): T[] {
  return [...similar].sort((a, b) => Number(!!b.card.action_taken) - Number(!!a.card.action_taken));
}
