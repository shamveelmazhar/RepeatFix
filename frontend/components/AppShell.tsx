"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { USE_MOCKS } from "@/lib/api";
import { CardViewerProvider } from "./CardViewer";
import { ChipIcon, GaugeIcon, MoonIcon, RepeatIcon, SunIcon, WrenchIcon } from "./icons";
import { LogoMark } from "./Logo";

const NAV = [
  { href: "/", label: "Fix a fault", icon: WrenchIcon },
  { href: "/repeats", label: "Repeat failures", icon: RepeatIcon },
  { href: "/results", label: "Results", icon: GaugeIcon },
];

function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2.5 text-xl font-bold tracking-tight">
      <LogoMark size={36} className="drop-shadow-sm" />
      RepeatFix
    </Link>
  );
}

function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => setDark(document.documentElement.classList.contains("dark")), []);
  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {
      // storage unavailable; theme still applies for this visit
    }
  };
  return (
    <button
      onClick={toggle}
      className="flex min-h-11 items-center gap-2 rounded-xl px-3 text-sm font-medium text-muted hover:bg-accent-soft hover:text-ink"
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
    >
      {dark ? <SunIcon /> : <MoonIcon />}
      <span className="hidden md:inline">{dark ? "Light mode" : "Dark mode"}</span>
    </button>
  );
}

function AmdBadge() {
  return (
    <div className="flex items-center gap-2.5 rounded-xl border border-line bg-accent-soft/60 px-3 py-2.5 text-sm text-muted">
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-gradient text-white">
        <ChipIcon width={18} height={18} />
      </span>
      <span>
        Runs on <strong className="text-ink">AMD Instinct MI300X</strong>
        <br />
        vLLM + ROCm
      </span>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <CardViewerProvider>
      <div className="min-h-screen md:flex">
        {/* Floating glass sidebar (tablet / desktop) */}
        <aside className="hidden w-64 shrink-0 p-4 pr-0 md:block">
          <div className="glass glass-strong sticky top-4 flex h-[calc(100vh-2rem)] flex-col justify-between rounded-3xl p-5">
            <div className="space-y-8">
              <Logo />
              <nav aria-label="Main" className="space-y-1.5">
                {NAV.map(({ href, label, icon: Icon }) => {
                  const active = pathname === href;
                  return (
                    <Link
                      key={href}
                      href={href}
                      aria-current={active ? "page" : undefined}
                      className={`flex min-h-12 items-center gap-3 rounded-xl px-3.5 font-medium transition-colors ${
                        active
                          ? "bg-accent-gradient text-on-accent shadow-md shadow-orange-600/20"
                          : "text-muted hover:bg-accent-soft hover:text-ink"
                      }`}
                    >
                      <Icon />
                      {label}
                    </Link>
                  );
                })}
              </nav>
            </div>
            <div className="space-y-3">
              <AmdBadge />
              <ThemeToggle />
            </div>
          </div>
        </aside>

        {/* Top bar + tabs (phone) */}
        <header className="glass glass-strong sticky top-0 z-20 rounded-none border-x-0 border-t-0 md:hidden">
          <div className="flex items-center justify-between px-4 py-3">
            <Logo />
            <ThemeToggle />
          </div>
          <nav aria-label="Main" className="flex border-t border-line">
            {NAV.map(({ href, label }) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={`flex-1 border-b-2 px-2 py-3 text-center text-sm font-medium ${
                    active ? "border-accent text-accent" : "border-transparent text-muted"
                  }`}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
        </header>

        <main className="min-w-0 flex-1 md:py-4 md:pr-4">
          {USE_MOCKS && (
            <div className="mx-4 mt-4 rounded-xl border border-warning/30 bg-warning-soft px-4 py-2 text-center text-sm text-warning md:mx-0 md:mt-0">
              Showing <strong>sample data</strong>. Connect the backend to see real FAA and NASA records.
            </div>
          )}
          <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-10 lg:px-8">{children}</div>
        </main>
      </div>
    </CardViewerProvider>
  );
}
