// ─────────────────────────────────────────────────────────────
// DEPARTURES design system — two fonts, one accent, six greys.
// Every visual constant lives here. No ad-hoc values elsewhere.
// ─────────────────────────────────────────────────────────────

export const ACCENT = "#d4a012";
export const WHITE = "#e8e4de";
export const BG = "#141414";
export const RED = "#b04040";
export const GREEN = "#5a8a5a";

// Grey palette — 6 stops, no ad-hoc values
export const G1 = "#999";
export const G2 = "#666";
export const G3 = "#444";
export const G4 = "#2a2a2a";
export const G5 = "#1a1a1a";
export const G6 = "#111";

export const DISPLAY = "'Disket Mono', monospace";
export const MONO = "'JetBrains Mono', monospace";

export const sys = (size, color = G3, extra = {}) => ({
  fontFamily: MONO, fontSize: size, color, letterSpacing: "0.04em", lineHeight: 1.2, ...extra,
});

export const inp = {
  background: G6, border: `1px solid ${G4}`, color: WHITE,
  fontFamily: MONO, fontSize: "11px", padding: "8px 12px",
  letterSpacing: "0.02em", outline: "none", width: "100%",
  boxSizing: "border-box", borderRadius: "4px",
};

export const STATUSES = ["QUEUED", "ACTIVE", "ROLLING", "BLOCKED", "REVIEW", "SHIPPED"];
export const TRACKS = ["01", "02", "03", "04", "05"];
export const DOMAINS = ["VFX", "AI", "WEB", "MIX", "OPS", "FAM"];

export const FONT_SIZES = [
  { label: "S", value: 64 },
  { label: "M", value: 104 },
  { label: "L", value: 140 },
];

export const SWATCHES = ["", "#1a1714", "#1a1318", "#141a18", "#18141a", "#1a1910", "#101820", "#201414", "#142014", "#141420", "#251a12", "#121a25", "#1a1225"];
