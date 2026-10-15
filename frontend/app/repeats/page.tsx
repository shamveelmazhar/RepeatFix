"use client";

import { Fragment, useEffect, useState } from "react";
import { useOpenCard } from "@/components/CardViewer";
import { ClockIcon, RepeatIcon, WrenchIcon } from "@/components/icons";
import { AtaTag, Panel, Skeleton, StatTile, StatusBadge, repeatSeverity } from "@/components/ui";
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
  // FAA SDR reports don't record downtime. Without it, rank and chart by how often a problem came back.
  const hasDowntime = totalDowntime > 0;
  const totalReports = rows?.reduce((s, r) => s + r.card_ids.length, 0) ?? 0;
  const top = rows?.[0];
  const assetHeading = groupBy === "aircraft" ? "Aircraft" : "Component";

  return (
    <div className="space-y-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Repeat failures</h1>
          <p className="mt-2 max-w-2xl text-lg text-muted">
            The same problem on the same {groupBy === "aircraft" ? "aircraft" : "component"}, logged more than once.
            Worst first, by {hasDowntime || !rows ? "total downtime" : "how often it came back"}.
          </p>
        </div>
        <div role="group" aria-label="Group by" className="glass inline-flex rounded-xl p-1">
          {(["aircraft", "component"] as GroupBy[]).map((g) => (
            <button
              key={g}
              onClick={() => setGroupBy(g)}
              aria-pressed={groupBy === g}
              className={`min-h-10 whitespace-nowrap rounded-lg px-4 font-medium ${
                groupBy === g ? "bg-accent-gradient text-on-accent shadow-sm" : "text-muted hover:text-ink"
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
        <StatTile
          tint="peach"
          icon={<RepeatIcon />}
          label="Repeat problems found"
          loading={!rows}
          value={rows ? String(rows.length) : null}
        />
        <StatTile
          tint="sand"
          icon={<ClockIcon />}
          label={hasDowntime || !rows ? "Downtime from repeats" : "Reports behind these repeats"}
          loading={!rows}
          value={rows ? (hasDowntime ? `${totalDowntime.toFixed(1)} h` : totalReports.toLocaleString()) : null}
          sub={rows && !hasDowntime ? "Downtime is not recorded in these reports" : undefined}
        />
        <StatTile
          tint="slate"
          icon={<WrenchIcon />}
          label="Worst offender"
          loading={!rows}
          value={top ? top.asset : rows ? "None" : null}
          sub={top ? `${failureModeLabel(top.failure_mode)} · ${top.count} times` : undefined}
        />
      </div>

      {rows && rows.length > 0 && <DowntimeChart rows={rows.slice(0, 8)} byCount={!hasDowntime} />}

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
                <li key={key} className="glass-inset lift rounded-xl p-4">
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
                    <div className="rounded-lg bg-white/40 py-2 dark:bg-white/5">
                      <dt className="text-xs text-muted">Times</dt>
                      <dd className="text-lg font-semibold">{r.count}</dd>
                    </div>
                    <div className="rounded-lg bg-white/40 py-2 dark:bg-white/5">
                      <dt className="text-xs text-muted">Avg days between</dt>
                      <dd className="text-lg font-semibold">{r.mtbf_days !== null ? Math.round(r.mtbf_days) : "—"}</dd>
                    </div>
                    <div className="rounded-lg bg-white/40 py-2 dark:bg-white/5">
                      <dt className="text-xs text-muted">Downtime</dt>
                      <dd className="text-lg font-semibold">{hasDowntime ? `${r.downtime_hours.toFixed(1)} h` : "—"}</dd>
                    </div>
                  </dl>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {r.card_ids.map((id) => (
                      <button
                        key={id}
                        onClick={() => openCard(id)}
                        className="glass-inset rounded-lg px-3 py-1.5 text-sm font-medium text-accent hover:border-accent"
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
                        className="cursor-pointer border-b border-line transition-colors hover:bg-accent-soft/50"
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
                        <td className="tabular px-3 py-3 text-right">{hasDowntime ? `${r.downtime_hours.toFixed(1)} h` : "—"}</td>
                        <td className="px-5 py-3 sm:px-6">
                          <StatusBadge severity={sev.severity}>{sev.label}</StatusBadge>
                        </td>
                      </tr>
                      {expanded && (
                        <tr className="border-b border-line bg-accent-soft/30">
                          <td colSpan={6} className="px-5 py-3 sm:px-6">
                            <p className="mb-2 text-sm font-medium text-muted">Job cards in this group (oldest first)</p>
                            <div className="flex flex-wrap gap-2">
                              {r.card_ids.map((id) => (
                                <button
                                  key={id}
                                  onClick={() => openCard(id)}
                                  className="glass-inset rounded-lg px-3 py-1.5 text-sm font-medium text-accent hover:border-accent"
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

/** Single-series horizontal bars: downtime per repeat problem (or times logged, when downtime isn't recorded). The table below is the full data view. */
function DowntimeChart({ rows, byCount = false }: { rows: RepeatRow[]; byCount?: boolean }) {
  const value = (r: RepeatRow) => (byCount ? r.count : r.downtime_hours);
  const max = Math.max(...rows.map(value), 1);
  const [hover, setHover] = useState<number | null>(null);
  return (
    <Panel title={byCount ? "Times each repeat problem was logged" : "Downtime from each repeat problem (hours)"}>
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
                className={`h-6 rounded-r-[4px] bg-brand-gradient transition-opacity ${hover !== null && hover !== i ? "opacity-40" : ""}`}
                style={{ width: `${(value(r) / max) * 85}%`, minWidth: 4 }}
              />
              <span className="tabular text-sm font-medium">{byCount ? r.count : r.downtime_hours.toFixed(1)}</span>
            </div>
            {hover === i && (
              <div className="glass glass-strong pointer-events-none absolute left-1/2 top-full z-10 mt-1 rounded-xl px-3 py-2 text-sm">
                <p className="font-semibold">
                  {r.asset} · {failureModeLabel(r.failure_mode)}
                </p>
                <p className="text-muted">
                  {r.count} times · every {r.mtbf_days !== null ? Math.round(r.mtbf_days) : "—"} days on average
                  {byCount ? "" : ` · ${r.downtime_hours.toFixed(1)} h down`}
                </p>
              </div>
            )}
          </li>
        ))}
      </ul>
    </Panel>
  );
}
