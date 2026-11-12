// ─────────────────────────────────────────────────────────────
// DEPARTURES design system — Direction 01, Calm Solari.
//
// Two fonts, one accent, one ink scale. Every visual constant
// lives here. No ad-hoc values elsewhere.
//
// Hierarchy is carried by SIZE and INK, not by fading text out:
//   shout    — split-flap project names (flapSize)
//   sentence — 14px (15px on the next-up card)
//   whisper  — 11px, #918D87, 5.1:1 or better on every surface
//
// Amber is spent once: the START HERE line and the next-up card.
// ─────────────────────────────────────────────────────────────

export const ACCENT = "#d4a012";      // START HERE + next-up card, nothing else
export const WHITE = "#e8e4de";       // speak: sentences, active status
export const WHISPER = "#918D87";     // 11px small text; quiet by size, not contrast
export const BG = "#141414";
export const RED = "#b04040";         // destructive affordance only, never text
export const GREEN = "#5a8a5a";
// Warnings the owner must be able to read at small sizes (5.3:1 on BG/panels).
export const RISK = "#d9705f";        // blocked / delayed / failures
export const NOTES_BG = "#1d1a17";    // warm dark, the back of a departure card
export const HOVER = "#1d1d1d";       // card hover surface; keeps whisper at 5.1:1

// Grey palette — 6 stops, no ad-hoc values
export const G1 = "#999";
export const G2 = "#666";
export const G3 = "#444";
export const G4 = "#2a2a2a";
export const G5 = "#1a1a1a";
export const G6 = "#111";

export const DISPLAY = "'Disket Mono', monospace";
export const MONO = "'JetBrains Mono', monospace";

// The two small tiers, in px. SHOUT lives with the flap size setting.
export const WHISPER_SIZE = 11;
export const SENTENCE_SIZE = 14;
export const NEXT_SENTENCE_SIZE = 15;

// A whisper is measured against every surface the board paints.
export const WHISPER_MIN_CONTRAST = 5.1;

export const sys = (size, color = G3, extra = {}) => ({
  fontFamily: MONO, fontSize: size, color, letterSpacing: "0.04em", lineHeight: 1.2, ...extra,
});

// Sentence tier: the next action, event names, the plain-words line.
export const sentence = (extra = {}) => sys(SENTENCE_SIZE, WHITE, { lineHeight: 1.5, ...extra });

// Whisper tier: metadata, counts, labels.
export const whisper = (extra = {}) => sys(WHISPER_SIZE, WHISPER, extra);

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

// ─── CONTRAST (WCAG 2.x) ───────────────────────────────────
// Exported so the token sheet is testable: a whisper that drops
// under 5.1:1 on any surface fails a test, not a design review.

const _linear = (c) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));

const _luminance = (hex) => {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const [r, g, b] = [0, 2, 4].map((i) => _linear(parseInt(full.slice(i, i + 2), 16) / 255));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

export function contrast(a, b) {
  const [hi, lo] = [_luminance(a), _luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}
