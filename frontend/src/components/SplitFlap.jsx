import { DISPLAY } from "../theme";

// ─── SPLIT FLAP DISPLAY ──────────────────────────────────────

export function FlapChar({ char, size, dim, flipping, delay }) {
  const s = typeof size === "number" ? size : 104;
  const moduleW = s * 0.7;
  const moduleH = s * 1.08;
  return (
    <div style={{
      width: moduleW, height: moduleH, background: dim ? "#131313" : "#171717",
      borderRadius: "4px", display: "flex", alignItems: "center", justifyContent: "center",
      position: "relative", overflow: "hidden", flexShrink: 0,
      boxShadow: dim ? "none" : "inset 0 1px 1px rgba(0,0,0,0.3), 0 1px 3px rgba(0,0,0,0.3)",
      animation: flipping ? `flapFlip 0.24s cubic-bezier(0.22,1,0.36,1) both` : "none",
      animationDelay: flipping ? `${delay || 0}ms` : "0ms",
    }}>
      <span style={{
        fontFamily: DISPLAY, fontSize: s, fontWeight: 400, color: dim ? "#1e1e1e" : "#c8c4bc",
        lineHeight: 1, position: "relative", zIndex: 1,
        WebkitTextStroke: dim ? "0" : `1px #c8c4bc`,
        textRendering: "optimizeLegibility",
      }}>
        {char === " " ? " " : char}
      </span>
      <div style={{
        position: "absolute", top: "50%", left: 0, right: 0, height: "3px",
        transform: "translateY(-1.5px)", zIndex: 2,
        background: dim ? "#0e0e0e" : "#0c0c0c",
        boxShadow: "0 1px 0 rgba(255,255,255,0.02), 0 -1px 0 rgba(0,0,0,0.5)",
      }} />
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: "50%",
        background: "linear-gradient(180deg, rgba(255,255,255,0.015) 0%, transparent 100%)",
        zIndex: 3, pointerEvents: "none",
      }} />
    </div>
  );
}

export function SplitFlapName({ text, shipped, flipping, size = 104, align = "left" }) {
  const justifyMap = { left: "flex-start", center: "center", right: "flex-end" };
  const chars = (text || "").toUpperCase().split("");
  return (
    <div style={{
      display: "flex", gap: "4px", overflow: "hidden", padding: "4px 0",
      justifyContent: justifyMap[align] || "flex-start",
    }}>
      {chars.map((ch, i) => (
        <FlapChar key={i} char={ch} size={size} dim={shipped} flipping={flipping} delay={i * 30} />
      ))}
    </div>
  );
}
