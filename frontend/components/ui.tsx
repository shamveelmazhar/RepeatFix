import type { ReactNode } from "react";
import { ataLabel } from "@/lib/ata";
import { AlertIcon, CheckIcon } from "./icons";

export function Panel({
  title,
  icon,
  action,
  children,
  lift = false,
  className = "",
}: {
  title?: string;
  icon?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  /** Grow slightly on hover. Use for result cards, not for forms. */
  lift?: boolean;
  className?: string;
}) {
  return (
    <section className={`glass rounded-2xl p-5 sm:p-6 ${lift ? "lift" : ""} ${className}`}>
      {title && (
        <div className="-mx-5 mb-5 flex items-center justify-between gap-3 border-b border-line px-5 pb-4 sm:-mx-6 sm:px-6">
          <h2 className="flex items-center gap-3 text-lg font-semibold">
            {icon && (
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-brand-gradient text-white shadow-sm shadow-orange-600/30">
                {icon}
              </span>
            )}
            {title}
          </h2>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function AtaTag({ chapter, name }: { chapter: string; name?: string }) {
  return (
    <span className="inline-flex items-center rounded-md border border-line bg-surface/70 px-2 py-0.5 text-sm font-medium text-ink">
      {ataLabel(chapter, name)}
    </span>
  );
}

type Severity = "critical" | "warning" | "ok" | "neutral";

const SEVERITY_STYLE: Record<Severity, string> = {
  critical: "bg-critical-soft text-critical border-critical/30",
  warning: "bg-warning-soft text-warning border-warning/30",
  ok: "bg-ok-soft text-ok border-ok/30",
  neutral: "bg-surface/70 text-muted border-line",
};

/** Status colours always come with an icon and a word, never colour alone. */
export function StatusBadge({ severity, children }: { severity: Severity; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-sm font-semibold ${SEVERITY_STYLE[severity]}`}
    >
      {severity === "ok" ? (
        <CheckIcon width={14} height={14} />
      ) : severity !== "neutral" ? (
        <AlertIcon width={14} height={14} />
      ) : null}
      {children}
    </span>
  );
}

export function repeatSeverity(count: number): { severity: Severity; label: string } {
  if (count >= 4) return { severity: "critical", label: "Critical" };
  if (count === 3) return { severity: "warning", label: "Watch" };
  return { severity: "neutral", label: "Repeat" };
}

export function Button({
  children,
  variant = "primary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" }) {
  const styles = {
    primary: "bg-accent-gradient text-on-accent shadow-md shadow-orange-700/25 hover:brightness-110 disabled:opacity-50 disabled:shadow-none",
    secondary: "border border-line bg-surface/80 text-ink hover:border-accent hover:text-accent disabled:opacity-50",
    ghost: "text-accent hover:bg-accent-soft",
  }[variant];
  return (
    <button
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 py-2 font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed ${styles} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function formatDate(iso: string | null): string {
  if (!iso) return "Date unknown";
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-line/70 ${className}`} />;
}
