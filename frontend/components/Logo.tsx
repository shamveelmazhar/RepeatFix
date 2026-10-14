import { useId } from "react";

// RepeatFix mark: two circular "repeat" arrows with a wrench through the gap.
// The wrench is knocked out of the arrows (negative space) so the two shapes read separately.
// Geometry lives in a 64×64 box; keep public/icon.svg in sync if you change it.

const TOP_ARC = "M40.45 16.11 A18 18 0 0 0 14 32";
const BOTTOM_ARC = "M23.55 47.89 A18 18 0 0 0 50 32";
const ARROWHEADS = "M7 31 L21 31 L14 41 Z M43 33 L57 33 L50 23 Z";

// Wrench drawn horizontally around the origin, then rotated onto the 45° gap.
function Wrench({ extra = 0 }: { extra?: number }) {
  return (
    <g transform="translate(32 32) rotate(-45)">
      <rect x={-19 - extra} y={-2.6 - extra} width={32 + extra * 2} height={5.2 + extra * 2} rx={2.6 + extra} />
      <path
        d="M20.45 2.89 A4.5 4.5 0 1 1 20.45 -2.89"
        fill="none"
        stroke="currentColor"
        strokeWidth={4.2 + extra * 2}
      />
    </g>
  );
}

export function LogoMark({ size = 32, className = "" }: { size?: number; className?: string }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={className} role="img" aria-label="RepeatFix logo">
      <defs>
        <linearGradient id={`g${id}`} x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#FB923C" />
          <stop offset="0.55" stopColor="#EA580C" />
          <stop offset="1" stopColor="#9A3412" />
        </linearGradient>
        <mask id={`m${id}`} maskUnits="userSpaceOnUse" x="0" y="0" width="64" height="64">
          <rect width="64" height="64" fill="white" />
          <g fill="black" color="black">
            <Wrench extra={2.2} />
          </g>
        </mask>
      </defs>
      <rect width="64" height="64" rx="15" fill={`url(#g${id})`} />
      <g mask={`url(#m${id})`} fill="white">
        <path d={TOP_ARC} fill="none" stroke="white" strokeWidth="6" />
        <path d={BOTTOM_ARC} fill="none" stroke="white" strokeWidth="6" />
        <path d={ARROWHEADS} />
      </g>
      <g fill="white" color="white">
        <Wrench />
      </g>
    </svg>
  );
}
