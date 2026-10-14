// ATA iSpec 2200 chapter names. Always show a chapter with its name.
const ATA_NAMES: Record<string, string> = {
  "05": "Time Limits / Inspections",
  "12": "Servicing",
  "21": "Air Conditioning & Pressurization",
  "22": "Auto Flight",
  "23": "Communications",
  "24": "Electrical Power",
  "25": "Equipment / Furnishings",
  "26": "Fire Protection",
  "27": "Flight Controls",
  "28": "Fuel",
  "29": "Hydraulic Power",
  "30": "Ice & Rain Protection",
  "31": "Indicating / Recording",
  "32": "Landing Gear",
  "33": "Lights",
  "34": "Navigation",
  "35": "Oxygen",
  "36": "Pneumatic",
  "38": "Water / Waste",
  "49": "Auxiliary Power Unit",
  "52": "Doors",
  "53": "Fuselage",
  "55": "Stabilizers",
  "56": "Windows",
  "57": "Wings",
  "61": "Propellers",
  "71": "Power Plant",
  "72": "Engine",
  "73": "Engine Fuel & Control",
  "74": "Ignition",
  "75": "Engine Air",
  "76": "Engine Controls",
  "77": "Engine Indicating",
  "78": "Exhaust",
  "79": "Oil",
  "80": "Starting",
};

export function ataName(chapter: string, fallback?: string): string {
  const key = chapter.padStart(2, "0");
  return fallback ?? ATA_NAMES[key] ?? "Other";
}

export function ataLabel(chapter: string, fallback?: string): string {
  return `ATA ${chapter.padStart(2, "0")} – ${ataName(chapter, fallback)}`;
}

export const SOURCE_LABEL: Record<string, string> = {
  sdr: "FAA Service Difficulty Report",
  asrs: "NASA ASRS report",
  photo: "Photographed log entry",
  text: "Typed entry",
};
