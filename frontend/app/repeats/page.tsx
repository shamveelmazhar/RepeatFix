"use client";

import { Fragment, useEffect, useState } from "react";
import { useOpenCard } from "@/components/CardViewer";
import { AtaTag, Panel, Skeleton, StatusBadge, repeatSeverity } from "@/components/ui";
import { api } from "@/lib/api";
import { failureModeLabel } from "@/lib/mock";
import type { GroupBy, RepeatRow } from "@/lib/types";

export default function RepeatFailuresPage() {
  const [groupBy, setGroupBy] = useState<GroupBy>("aircraft");
  const [rows, setRows] = useState<RepeatRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const openCard = useOpenCard();

  useEffect(() => {
    setRows(null);
    setError(null);
    setOpen(null);
    api
      .getRepeats(groupBy)
      .then(setRows)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load repeat failures."));
  }, [groupBy]);

  const totalDowntime = rows?.reduce((s, r) => s + r.downtime_hours, 0) ?? 0;
  const top = rows?.[0];
  const assetHeading = groupBy === "aircraft" ? "Aircraft" : "Component";

  return (
    <div className="space-y-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Repeat failures</h1>
          <p className="mt-2 max-w-2xl text-lg text-muted">
            The same problem on the same {groupBy === "aircraft" ? "aircraft" : "component"}, logged more than once.
            Worst first, by total downtime.
          </p>
        </div>
        <div role="group" aria-label="Group by" className="inline-flex rounded-lg border border-line bg-surface p-1">
          {(["aircraft", "component"] as GroupBy[]).map((g) => (
            <button
              key={g}
              onClick={() => setGroupBy(g)}
              aria-pressed={groupBy === g}
              className={`min-h-10 whitespace-nowrap rounded-md px-4 font-medium ${
                groupBy === g ? "bg-accent text-on-accent" : "text-muted hover:text-ink"
              }`}
            >
              By {g}
            </button>
          ))}
        </div>
      </header>

      {error && (
        <p role="alert" className="rounded-xl border border-critical/30 bg-critical-soft p-4 text-critical">
          {error}
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Stat label="Repeat problems found" value={rows ? String(rows.length) : null} />
        <Stat label="Downtime from repeats" value={rows ? `${totalDowntime.toFixed(1)} h` : null} />
        <Stat
          label="Worst offender"
          value={top ? top.asset : rows ? "None" : null}
          sub={top ? `${failureModeLabel(top.failure_mode)} · ${top.count} times` : undefined}
        />
      </div>

      {rows && rows.length > 0 && <DowntimeChart rows={rows.slice(0, 8)} />}

      <Panel title={`All repeat problems by ${groupBy}`}>
        {!rows ? (
          <div className="space-y-3">
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
          </div>
        ) : rows.length === 0 ? (
          <p className="text-muted">No repeat failures found.</p>
        ) : (
          <>
          {/* Phone and tablet: one card per repeat problem */}
          <ul className="space-y-3 lg:hidden">
            {rows.map((r) => {
              const key = `${r.asset}|${r.failure_mode}`;
              const sev = repeatSeverity(r.count);
              return (
                <li key={key} className="rounded-lg border border-line p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold">
                        {r.asset} <span className="font-normal text-muted">· {r.aircraft_type}</span>
                      </p>
                      <p className="font-medium">{failureModeLabel(r.failure_mode)}</p>
                    </div>
                    <StatusBadge severity={sev.severity}>{sev.label}</StatusBadge>
                  </div>
                  <div className="mt-2">
                    <AtaTag chapter={r.ata_chapter} name={r.ata_name} />
                  </div>
                  <dl className="tabular mt-3 grid grid-cols-3 gap-2 text-center">
                    <div className="rounded-md bg-bg py-2">
                      <dt className="text-xs text-muted">Times</dt>
                      <dd className="text-lg font-semibold">{r.count}</dd>
                    </div>
                    <div className="rounded-md bg-bg py-2">
                      <dt className="text-xs text-muted">Avg days between</dt>
                      <dd className="text-lg font-semibold">{r.mtbf_days !== null ? Math.round(r.mtbf_days) : "—"}</dd>
                    </div>
                    <div className="rounded-md bg-bg py-2">
                      <dt className="text-xs text-muted">Downtime</dt>
                      <dd className="text-lg font-semibold">{r.downtime_hours.toFixed(1)} h</dd>
                    </div>
                  </dl>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {r.card_ids.map((id) => (
                      <button
                        key={id}
                        onClick={() => openCard(id)}
                        className="rounded-md border border-line px-3 py-1.5 text-sm font-medium text-accent hover:border-accent"
                      >
                        {id}
                      </button>
                    ))}
                  </div>
                </li>
              );
            })}
          </ul>

          {/* Desktop: full table */}
          <div className="-mx-5 hidden overflow-x-auto sm:-mx-6 lg:block">
            <table className="w-full min-w-[720px] text-left">
              <thead>
                <tr className="border-b border-line text-sm text-muted">
                  <th className="px-5 py-2 font-medium sm:px-6">{assetHeading}</th>
                  <th className="px-3 py-2 font-medium">Problem</th>
                  <th className="px-3 py-2 text-right font-medium">Times</th>
                  <th className="px-3 py-2 text-right font-medium">Avg days between</th>
                  <th className="px-3 py-2 text-right font-medium">Downtime</th>
                  <th className="px-5 py-2 font-medium sm:px-6">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const key = `${r.asset}|${r.failure_mode}`;
                  const sev = repeatSeverity(r.count);
                  const expanded = open === key;
                  return (
                    <Fragment key={key}>
                      <tr
                        onClick={() => setOpen(expanded ? null : key)}
                        className="cursor-pointer border-b border-line hover:bg-bg"
                        aria-expanded={expanded}
                      >
                        <td className="px-5 py-3 sm:px-6">
                          <p className="font-semibold">{r.asset}</p>
                          <p className="text-sm text-muted">{r.aircraft_type}</p>
                        </td>
                        <td className="px-3 py-3">
                          <p className="font-medium">{failureModeLabel(r.failure_mode)}</p>
                          <div className="mt-1">
                            <AtaTag chapter={r.ata_chapter} name={r.ata_name} />
                          </div>
                        </td>
                        <td className="tabular px-3 py-3 text-right text-lg font-semibold">{r.count}</td>
                        <td className="tabular px-3 py-3 text-right">{r.mtbf_days !== null ? Math.round(r.mtbf_days) : "—"}</td>
                        <td className="tabular px-3 py-3 text-right">{r.downtime_hours.toFixed(1)} h</td>
                        <td className="px-5 py-3 sm:px-6">
                          <StatusBadge severity={sev.severity}>{sev.label}</StatusBadge>
                        </td>
                      </tr>
                      {expanded && (
                        <tr className="border-b border-line bg-bg">
                          <td colSpan={6} className="px-5 py-3 sm:px-6">
                            <p className="mb-2 text-sm font-medium text-muted">Job cards in this group (oldest first)</p>
                            <div className="flex flex-wrap gap-2">
                              {r.card_ids.map((id) => (
                                <button
                                  key={id}
                                  onClick={() => openCard(id)}
                                  className="rounded-md border border-line bg-surface px-3 py-1.5 text-sm font-medium text-accent hover:border-accent"
                                >
                                  {id}
                                </button>
                              ))}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
          </>
        )}
      </Panel>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string | null; sub?: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-5">
      <p className="text-sm font-medium text-muted">{label}</p>
      {value === null ? (
        <Skeleton className="mt-2 h-9 w-24" />
      ) : (
        <p className="tabular mt-1 text-3xl font-bold">{value}</p>
      )}
      {sub && <p className="mt-1 text-sm text-muted">{sub}</p>}
    </div>
  );
}

/** Single-series horizontal bars: downtime per repeat problem. The table below is the full data view. */
function DowntimeChart({ rows }: { rows: RepeatRow[] }) {
  const max = Math.max(...rows.map((r) => r.downtime_hours), 1);
  const [hover, setHover] = useState<number | null>(null);
  return (
    <Panel title="Downtime from each repeat problem (hours)">
      <ul className="space-y-1">
        {rows.map((r, i) => (
          <li
            key={`${r.asset}|${r.failure_mode}`}
            className="relative grid grid-cols-[minmax(0,10rem)_1fr] items-center gap-3 rounded-md py-1.5 sm:grid-cols-[minmax(0,16rem)_1fr]"
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
          >
            <span className="truncate text-sm">
              <span className="font-semibold">{r.asset}</span>{" "}
              <span className="text-muted">{failureModeLabel(r.failure_mode)}</span>
            </span>
            <div className="flex items-center gap-2">
              <div
                className={`h-6 rounded-r-[4px] bg-accent transition-opacity ${hover !== null && hover !== i ? "opacity-40" : ""}`}
                style={{ width: `${(r.downtime_hours / max) * 85}%`, minWidth: 4 }}
              />
              <span className="tabular text-sm font-medium">{r.downtime_hours.toFixed(1)}</span>
            </div>
            {hover === i && (
              <div className="pointer-events-none absolute left-1/2 top-full z-10 mt-1 rounded-lg border border-line bg-surface px-3 py-2 text-sm shadow-lg">
                <p className="font-semibold">
                  {r.asset} · {failureModeLabel(r.failure_mode)}
                </p>
                <p className="text-muted">
                  {r.count} times · every {r.mtbf_days !== null ? Math.round(r.mtbf_days) : "—"} days on average · {r.downtime_hours.toFixed(1)} h down
                </p>
              </div>
            )}
          </li>
        ))}
      </ul>
    </Panel>
  );
}
