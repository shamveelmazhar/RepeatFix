// ATA iSpec 2200 chapter names, same list as backend/app/vocab.py. Always show a chapter with its name.
const ATA_NAMES: Record<string, string> = {
  "00": "General / Ground Operations",
  "05": "Time Limits / Inspections",
  "11": "Placards & Markings",
  "12": "Servicing",
  "14": "Hardware",
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
  "37": "Vacuum",
  "38": "Water / Waste",
  "45": "Central Maintenance System",
  "49": "Auxiliary Power Unit",
  "51": "Structures – General",
  "52": "Doors",
  "53": "Fuselage",
  "54": "Nacelles / Pylons",
  "55": "Stabilizers",
  "56": "Windows",
  "57": "Wings",
  "61": "Propellers",
  "62": "Main Rotor",
  "63": "Main Rotor Drive",
  "64": "Tail Rotor",
  "65": "Tail Rotor Drive",
  "67": "Rotors Flight Control",
  "71": "Power Plant",
  "72": "Engine",
  "73": "Engine Fuel & Control",
  "74": "Ignition",
  "75": "Engine Air",
  "76": "Engine Controls",
  "77": "Engine Indicating",
  "78": "Exhaust / Thrust Reverser",
  "79": "Oil",
  "80": "Starting",
  "81": "Turbines",
  "82": "Water Injection",
  "83": "Accessory Gearboxes",
  "85": "Reciprocating Engine",
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
