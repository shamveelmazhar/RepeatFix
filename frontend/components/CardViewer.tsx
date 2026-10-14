"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { SOURCE_LABEL } from "@/lib/ata";
import { failureModeLabel } from "@/lib/mock";
import type { JobCard } from "@/lib/types";
import { XIcon } from "./icons";
import { AtaTag, formatDate } from "./ui";

const CardViewerContext = createContext<(id: string) => void>(() => {});

/** Lets any screen open a past job card (the evidence behind an answer). */
export function useOpenCard() {
  return useContext(CardViewerContext);
}

export function CardViewerProvider({ children }: { children: ReactNode }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [card, setCard] = useState<JobCard | null>(null);
  const [missing, setMissing] = useState(false);

  const open = useCallback((id: string) => {
    setCard(null);
    setMissing(false);
    dialogRef.current?.showModal();
    api
      .getCard(id)
      .then((c) => (c ? setCard(c) : setMissing(true)))
      .catch(() => setMissing(true));
  }, []);

  useEffect(() => {
    const d = dialogRef.current;
    const onClick = (e: MouseEvent) => {
      if (e.target === d) d?.close();
    };
    d?.addEventListener("click", onClick);
    return () => d?.removeEventListener("click", onClick);
  }, []);

  return (
    <CardViewerContext.Provider value={open}>
      {children}
      <dialog
        ref={dialogRef}
        aria-label="Past job card"
        className="m-auto w-[min(640px,calc(100vw-2rem))] rounded-2xl border border-line bg-surface p-0 text-ink shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4 border-b border-line p-5">
          <div>
            <p className="text-sm text-muted">Past job card</p>
            <h2 className="text-xl font-semibold">{card ? card.symptom : missing ? "Card not found" : "Loading…"}</h2>
          </div>
          <button
            onClick={() => dialogRef.current?.close()}
            className="rounded-lg p-2 text-muted hover:bg-bg hover:text-ink"
            aria-label="Close"
          >
            <XIcon />
          </button>
        </div>
        {card && (
          <div className="space-y-4 p-5">
            <div className="flex flex-wrap gap-2">
              <AtaTag chapter={card.ata_chapter} name={card.ata_name} />
              <span className="rounded-md border border-line px-2 py-0.5 text-sm text-muted">
                {failureModeLabel(card.failure_mode)}
              </span>
            </div>
            <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
              <Field label="Aircraft" value={`${card.registration ?? "Tail not recorded"} · ${card.aircraft_type}`} />
              <Field label="Date" value={formatDate(card.date)} />
              <Field label="Component" value={card.component} />
              <Field
                label="Downtime"
                value={card.downtime_hours !== null ? `${card.downtime_hours} hours` : "Not recorded"}
              />
              <Field label="What was done" value={card.action_taken || "Not recorded"} wide />
              {card.parts.length > 0 && <Field label="Parts" value={card.parts.join(", ")} wide />}
            </dl>
            <div>
              <p className="mb-1 text-sm font-medium text-muted">Original entry</p>
              <p className="rounded-lg bg-bg p-3 font-mono text-sm leading-relaxed">{card.raw_text}</p>
            </div>
            <p className="text-sm text-muted">
              Source: {SOURCE_LABEL[card.source] ?? card.source} · {card.id}
            </p>
          </div>
        )}
      </dialog>
    </CardViewerContext.Provider>
  );
}

function Field({ label, value, wide }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={wide ? "sm:col-span-2" : ""}>
      <dt className="text-sm font-medium text-muted">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
