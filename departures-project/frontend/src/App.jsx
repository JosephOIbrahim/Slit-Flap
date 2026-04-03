import { useState, useEffect, useRef } from "react";

// ─────────────────────────────────────────────────────────────
// DEPARTURES v0.4 — DESIGN TIGHTENING PASS + FEATURES
//
// Pentagram principles applied: earned space, shout/whisper,
// one grid, color as information, motion as punctuation,
// empty states designed, invisible details resolved.
//
// v0.4 adds: editable events, weather widget, font size +
// alignment controls. All controls whisper-volume (7-9px).
// ─────────────────────────────────────────────────────────────

const ACCENT = "#d4a012";
const WHITE = "#e8e4de";
const BG = "#141414";

// Grey palette — 6 stops, no ad-hoc values
const G1 = "#999";
const G2 = "#666";
const G3 = "#444";
const G4 = "#2a2a2a";
const G5 = "#1a1a1a";
const G6 = "#111";

const DISPLAY = "'Disket Mono', monospace";
const MONO = "'JetBrains Mono', monospace";
const sys = (size, color = G3, extra = {}) => ({ fontFamily: MONO, fontSize: size, color, letterSpacing: "0.04em", lineHeight: 1.2, ...extra });

const STATUSES = ["QUEUED", "ACTIVE", "ROLLING", "BLOCKED", "REVIEW", "SHIPPED"];
const TRACKS = ["01", "02", "03", "04", "05"];
const DOMAINS = ["VFX", "AI", "WEB", "MIX", "OPS", "FAM"];

const FONT_SIZES = [
  { label: "S", value: 64 },
  { label: "M", value: 104 },
  { label: "L", value: 140 },
];

// ─── WEATHER ─────────────────────────────────────────────────

const WMO_DESC = {0:"Clear",1:"Mostly Clear",2:"Partly Cloudy",3:"Overcast",45:"Fog",48:"Rime Fog",51:"Lt Drizzle",53:"Drizzle",55:"Hvy Drizzle",61:"Lt Rain",63:"Rain",65:"Hvy Rain",71:"Lt Snow",73:"Snow",75:"Hvy Snow",80:"Showers",95:"Thunderstorm"};

async function fetchWeather(zip) {
  if (!zip || zip.length < 5) return null;
  try {
    const geo = await fetch(`https://api.zippopotam.us/us/${zip}`).then(r => { if(!r.ok) throw null; return r.json(); });
    const place = geo.places[0];
    const city = place["place name"];
    const state = place["state abbreviation"];
    const lat = parseFloat(place.latitude);
    const lon = parseFloat(place.longitude);
    const wx = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true&temperature_unit=fahrenheit`).then(r=>r.json());
    return { city: `${city}, ${state}`, temp: Math.round(wx.current_weather.temperature), desc: WMO_DESC[wx.current_weather.weathercode] || "" };
  } catch { return null; }
}

// ─── MOCK DATA ───────────────────────────────────────────────

// Mock emails (would come from Gmail MCP)
const MOCK_EMAILS = [
  { id: "em1", type: "email", time: "08:15", from: "USPTO", subject: "Patent filing confirmation — USD Cognitive Substrate", linkedProject: "patents" },
  { id: "em2", type: "email", time: "09:45", from: "Vercel", subject: "Deploy succeeded: jaimeibrahim.com", linkedProject: "jaime" },
  { id: "em3", type: "email", time: "12:20", from: "GitHub", subject: "New issue on Harlo: hippocampus decay test flaky", linkedProject: "cog-sub" },
];

// ─── NEXT UP SCORING ─────────────────────────────────────────
function scoreProject(p) {
  if (p.status === "SHIPPED" || p.status === "QUEUED") return -1;
  let score = 0;
  if (p.todayTime) score += 100;
  if (p.status === "ACTIVE") score += 50;
  if (p.status === "ROLLING") score += 40;
  if (p.status === "BLOCKED") score += 5;
  if (p.track === "01") score += 30;
  else if (p.track === "02") score += 20;
  else if (p.track === "03") score += 10;
  const days = (Date.now() - new Date(p.lastTouched || p.updatedAt).getTime()) / 86400000;
  score += Math.min(days * 3, 40);
  return score;
}

// ─── RELATIVE TIME ───────────────────────────────────────────
function relTime(iso) {
  if (!iso) return "";
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return "1d ago";
  return `${days}d ago`;
}

// ─── SESSION PULSE ───────────────────────────────────────────
function sessionColor(mins) {
  if (mins < 120) return "#3a5a3a";
  if (mins < 240) return "#5a4a2a";
  return "#4a2a2a";
}

function formatDuration(mins) {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function statusColor(s) {
  if (s === "ACTIVE" || s === "ROLLING") return ACCENT;
  if (s === "BLOCKED") return "#b04040";
  if (s === "SHIPPED") return G3;
  return G4;
}

function timeToMinutes(t) {
  if (!t) return 9999;
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
}

function Progress({ mile, of: total }) {
  if (!total) return null;
  const pct = Math.round((mile / total) * 100);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <div style={{ width: "48px", height: "2px", background: G4, borderRadius: "4px", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: pct >= 100 ? "#5a8a5a" : ACCENT, transition: "width 0.48s ease" }} />
      </div>
      <span style={sys("9px", G4)}>{mile}/{total}</span>
    </div>
  );
}

// ─── SPLIT FLAP DISPLAY ──────────────────────────────────────

function FlapChar({ char, size, dim, flipping, delay }) {
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
        {char === " " ? "\u00A0" : char}
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

function SplitFlapName({ text, shipped, flipping, size = 104, align = "left" }) {
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

// ─── INPUT STYLE ─────────────────────────────────────────────

const inp = {
  background: G6, border: `1px solid ${G4}`, color: WHITE,
  fontFamily: MONO, fontSize: "11px", padding: "8px 12px",
  letterSpacing: "0.02em", outline: "none", width: "100%",
  boxSizing: "border-box", borderRadius: "4px",
};

const SWATCHES = ["", "#1a1714", "#1a1318", "#141a18", "#18141a", "#1a1910", "#101820", "#201414", "#142014", "#141420", "#251a12", "#121a25", "#1a1225"];

// ─── EVENT EDIT PANEL ────────────────────────────────────────

function EventEditPanel({ event, onUpdate, onDelete }) {
  const [draft, setDraft] = useState({
    time: event.time || "",
    endTime: event.endTime || event.end || "",
    name: event.name || "",
    linkedProject: event.linkedProject || "",
  });
  const d = (k, v) => setDraft(prev => ({ ...prev, [k]: v }));
  const save = () => onUpdate({ ...event, ...draft });
  return (
    <div style={{ padding: "12px 24px", borderTop: `1px solid ${G4}`, background: G6 }} onClick={e => e.stopPropagation()}>
      <div style={{ display: "grid", gridTemplateColumns: "60px 60px 1fr", gap: "8px", marginBottom: "8px" }}>
        <input value={draft.time} onChange={e => d("time", e.target.value)} onBlur={save} placeholder="HH:MM" style={inp} />
        <input value={draft.endTime} onChange={e => d("endTime", e.target.value)} onBlur={save} placeholder="END" style={inp} />
        <input value={draft.name} onChange={e => d("name", e.target.value)} onBlur={save} placeholder="Event name" style={inp} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <input value={draft.linkedProject} onChange={e => d("linkedProject", e.target.value)} onBlur={save} placeholder="Link to project ID" style={{ ...inp, width: "180px" }} />
        <button onClick={() => onDelete(event.id)}
          style={{ ...sys("9px", G3), background: "transparent", border: `1px solid ${G4}`, padding: "8px 12px", cursor: "pointer", borderRadius: "4px" }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = "#b04040"; e.currentTarget.style.color = "#b04040"; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = G4; e.currentTarget.style.color = G3; }}>
          DELETE
        </button>
      </div>
    </div>
  );
}

// ─── EDIT PANEL ──────────────────────────────────────────────

function EditPanel({ project, onUpdate, onDelete }) {
  const u = (k, v) => onUpdate({ ...project, [k]: v });
  return (
    <div style={{ padding: "18px 24px 18px", borderTop: `1px solid ${G4}`, background: G6 }} onClick={(e) => e.stopPropagation()}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "8px" }}>
        <input value={project.name} onChange={(e) => u("name", e.target.value)} placeholder="PROJECT" style={inp} />
        <input value={project.next} onChange={(e) => u("next", e.target.value)} placeholder="NEXT ACTION" style={inp} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "8px", marginBottom: "12px" }}>
        <select value={project.domain} onChange={(e) => u("domain", e.target.value)} style={inp}>
          {DOMAINS.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        <select value={project.track} onChange={(e) => u("track", e.target.value)} style={inp}>
          {TRACKS.map((t) => <option key={t} value={t}>TRK {t}</option>)}
        </select>
        <input type="date" value={project.deadline} onChange={(e) => u("deadline", e.target.value)} style={inp} />
        <div style={{ display: "flex", gap: "4px" }}>
          <input type="number" min="0" value={project.mile} onChange={(e) => u("mile", +e.target.value || 0)} placeholder="MI" style={{ ...inp, width: "50%" }} />
          <input type="number" min="0" value={project.of} onChange={(e) => u("of", +e.target.value || 0)} placeholder="OF" style={{ ...inp, width: "50%" }} />
        </div>
      </div>
      <div style={{ display: "flex", gap: "4px", alignItems: "center", marginBottom: "12px" }}>
        <span style={sys("9px", G3, { letterSpacing: "0.1em", marginRight: "8px" })}>BG</span>
        {SWATCHES.map((c, i) => (
          <button key={i} onClick={() => u("bgColor", c)} style={{
            width: "18px", height: "18px", borderRadius: "4px",
            border: project.bgColor === c ? `1px solid ${ACCENT}` : c ? `1px solid ${G4}` : `1px dashed ${G4}`,
            background: c || "transparent", cursor: "pointer", padding: 0,
          }} />
        ))}
        <input type="color" value={project.bgColor || "#191919"} onChange={(e) => u("bgColor", e.target.value)}
          style={{ width: "18px", height: "18px", border: "none", background: "none", cursor: "pointer", padding: 0, marginLeft: "4px" }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={sys("9px", G4)}>/{project.id} · {project.history.length} transitions</span>
        <button onClick={() => onDelete(project.id)}
          style={{ ...sys("9px", G3), background: "transparent", border: `1px solid ${G4}`, padding: "8px 12px", cursor: "pointer", borderRadius: "4px" }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#b04040"; e.currentTarget.style.color = "#b04040"; }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = G4; e.currentTarget.style.color = G3; }}>
          ARCHIVE
        </button>
      </div>
    </div>
  );
}

// ─── PROJECT ROW (TIER 1 — SHOUT) ───────────────────────────

function ProjectRow({ project, onUpdate, onDelete, open, onToggle, showTime, isNextUp, flapSize, flapAlign, readOnly }) {
  const shipped = project.status === "SHIPPED";
  const [flipping, setFlipping] = useState(false);

  const triggerFlip = () => {
    setFlipping(true);
    setTimeout(() => setFlipping(false), 400);
  };

  const cycleStatus = (e) => {
    e.stopPropagation();
    if (readOnly) return;
    const i = STATUSES.indexOf(project.status);
    const next = STATUSES[(i + 1) % STATUSES.length];
    triggerFlip();
    onUpdate({
      ...project, status: next, updatedAt: new Date().toISOString(),
      lastTouched: new Date().toISOString(),
      history: [...project.history, { from: project.status, to: next, at: new Date().toISOString() }],
    });
  };

  const handleToggle = () => {
    if (!open) {
      triggerFlip();
      if (!readOnly) onUpdate({ ...project, lastTouched: new Date().toISOString() });
    }
    onToggle();
  };

  const addLogEntry = (text) => {
    if (!text.trim()) return;
    fetch(`/api/projects/${project.id}/logs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    })
      .then(r => r.json())
      .then(entry => {
        onUpdate({
          ...project,
          log: [...(project.log || []), entry],
          lastTouched: new Date().toISOString(),
        });
      });
  };

  return (
    <div style={{
      background: project.bgColor || G5, borderRadius: "4px",
      cursor: "pointer", transition: "all 0.28s cubic-bezier(0.22, 1, 0.36, 1)",
      position: "relative", zIndex: 1, overflow: "hidden",
      borderLeft: isNextUp ? `3px solid ${ACCENT}` : "3px solid transparent",
    }}
      onClick={handleToggle}
      onMouseEnter={(e) => { const el = e.currentTarget; if (!shipped) { el.style.transform = "scale(1.005) translateY(-2px)"; el.style.boxShadow = `0 4px 20px rgba(0,0,0,0.5), 0 0 0 1px ${G4}`; el.style.zIndex = "10"; el.style.background = project.bgColor || "#202020"; } }}
      onMouseLeave={(e) => { const el = e.currentTarget; el.style.transform = "scale(1) translateY(0)"; el.style.boxShadow = "none"; el.style.zIndex = "1"; el.style.background = project.bgColor || G5; }}>

      <div style={{
        padding: "18px 24px", minHeight: "180px", display: "flex", flexDirection: "column",
        justifyContent: "space-between", opacity: shipped ? 0.35 : 1, transition: "opacity 0.24s",
      }}>
        {/* Top whisper */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            {showTime && project.todayTime ? (
              <span style={sys("9px", G2, { fontWeight: 600 })}>{project.todayTime}</span>
            ) : (
              <span style={sys("9px", G3)}>{project.track}</span>
            )}
            <span style={sys("9px", G4, { letterSpacing: "0.08em" })}>{project.domain}</span>
            <span style={sys("9px", G4)}>{relTime(project.lastTouched)}</span>
          </div>
          <button onClick={cycleStatus} style={{
            background: "transparent", border: "none", fontFamily: MONO, fontSize: "9px", fontWeight: 600,
            color: statusColor(project.status), letterSpacing: "0.1em", cursor: readOnly ? "default" : "pointer",
            padding: "8px 4px", margin: "-8px -4px",
          }}>{project.status}</button>
        </div>
        {/* Name shout — split flap display */}
        <div style={{ padding: "4px 0" }}>
          <SplitFlapName text={project.name} shipped={shipped} flipping={flipping} size={flapSize || 104} align={flapAlign || "left"} />
        </div>
        {/* Bottom whisper */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", minHeight: "12px" }}>
          {project.next ? <span style={sys("9px", G3, { flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{project.next}</span> : <span />}
          {project.of > 0 && <Progress mile={project.mile} of={project.of} />}
        </div>
      </div>

      {/* Edit panel + log */}
      {open && (
        <>
          {!readOnly && <EditPanel project={project} onUpdate={onUpdate} onDelete={onDelete} />}
          <LogPanel log={project.log || []} onAdd={addLogEntry} readOnly={readOnly} />
        </>
      )}
    </div>
  );
}

// ─── EVENT ROW (TIER 2 — SPEAK) ─────────────────────────────

function EventRow({ event, open, onToggle, onUpdate, onDelete, readOnly }) {
  const linked = event.linkedProject;
  return (
    <div style={{
      background: G5, borderRadius: "4px", overflow: "hidden",
      transition: "all 0.24s cubic-bezier(0.22, 1, 0.36, 1)",
      cursor: "pointer",
    }}>
      <div style={{
        padding: "12px 24px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}
        onClick={onToggle}
        onMouseEnter={(e) => { e.currentTarget.parentElement.style.background = "#202020"; }}
        onMouseLeave={(e) => { e.currentTarget.parentElement.style.background = G5; }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", flex: 1, minWidth: 0 }}>
          <span style={sys("9px", G2, { fontWeight: 600, minWidth: "36px" })}>{event.time}</span>
          <span style={{
            fontFamily: MONO, fontSize: "9px", fontWeight: 400, color: G1,
            letterSpacing: "0.04em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>{event.name}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", flexShrink: 0 }}>
          {linked && <span style={sys("9px", G3, { letterSpacing: "0.08em" })}>→ {linked}</span>}
          <span style={sys("9px", G4, { letterSpacing: "0.06em" })}>{event.endTime || event.end}</span>
        </div>
      </div>
      {open && !readOnly && <EventEditPanel event={event} onUpdate={onUpdate} onDelete={onDelete} />}
    </div>
  );
}

// ─── EMAIL ROW (TIER 3 — WHISPER) ────────────────────────────

function EmailRow({ email }) {
  return (
    <div style={{
      background: "transparent", borderRadius: "4px", padding: "8px 24px",
      display: "flex", alignItems: "center", justifyContent: "space-between",
      borderLeft: `2px solid ${email.linkedProject ? G4 : G5}`,
      marginLeft: "12px",
      transition: "all 0.24s",
    }}
      onMouseEnter={(e) => { e.currentTarget.style.background = G5; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}>
      <div style={{ display: "flex", alignItems: "center", gap: "12px", flex: 1, minWidth: 0 }}>
        <span style={sys("9px", G3, { minWidth: "36px" })}>{email.time}</span>
        <span style={sys("9px", G3, { fontWeight: 600 })}>{email.from}</span>
        <span style={sys("9px", G4, { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 })}>{email.subject}</span>
      </div>
      {email.linkedProject && <span style={sys("9px", G4, { letterSpacing: "0.06em" })}>→ {email.linkedProject}</span>}
    </div>
  );
}

// ─── NOW LINE ────────────────────────────────────────────────

function NowLine() {
  const [now, setNow] = useState(new Date());
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 60000); return () => clearInterval(t); }, []);
  const h = now.getHours().toString().padStart(2, "0");
  const m = now.getMinutes().toString().padStart(2, "0");
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "12px", padding: "4px 36px", margin: "4px 0" }}>
      <span style={sys("9px", ACCENT, { fontWeight: 700 })}>NOW {h}:{m}</span>
      <div style={{ flex: 1, height: "1px", background: `linear-gradient(to right, ${ACCENT}, transparent)` }} />
    </div>
  );
}

// ─── SECTION LABEL ───────────────────────────────────────────

function SectionLabel({ label }) {
  return (
    <div style={{ padding: "12px 36px 4px" }}>
      <span style={sys("9px", G4, { letterSpacing: "0.14em", textTransform: "uppercase" })}>{label}</span>
    </div>
  );
}

// ─── LOG PANEL ───────────────────────────────────────────────

function LogPanel({ log, onAdd, readOnly }) {
  const [text, setText] = useState("");
  return (
    <div style={{ padding: "0 24px 18px", background: G6 }} onClick={(e) => e.stopPropagation()}>
      {!readOnly && (
        <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
          <input value={text} onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { onAdd(text); setText(""); } }}
            placeholder="Log a note..." style={{ ...inp, flex: 1 }} />
          <button onClick={() => { onAdd(text); setText(""); }}
            style={{ ...inp, width: "auto", cursor: "pointer", color: ACCENT, padding: "8px 12px" }}>+</button>
        </div>
      )}
      {log.length > 0 && (
        <div style={{ maxHeight: "120px", overflowY: "auto" }}>
          {[...log].reverse().slice(0, 8).map((entry, i) => (
            <div key={i} style={{ display: "flex", gap: "8px", padding: "4px 0" }}>
              <span style={sys("9px", G3, { minWidth: "36px", flexShrink: 0 })}>{relTime(entry.at)}</span>
              <span style={sys("9px", G3)}>{entry.text}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── DAILY RECAP ─────────────────────────────────────────────

function RecapPanel({ projects, sessionMins, onClose }) {
  const today = new Date().toDateString();
  const touched = projects.filter((p) => {
    if (!p.lastTouched) return false;
    return new Date(p.lastTouched).toDateString() === today;
  });
  const shipped = touched.filter((p) => p.status === "SHIPPED");

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", zIndex: 200,
      display: "flex", alignItems: "center", justifyContent: "center", padding: "24px",
    }} onClick={onClose}>
      <div style={{
        background: G5, borderRadius: "4px", padding: "36px", maxWidth: "480px", width: "100%",
        border: `1px solid ${G4}`,
      }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "18px" }}>
          <span style={{ fontFamily: DISPLAY, fontSize: "18px", color: WHITE, letterSpacing: "0.1em", textTransform: "uppercase", textRendering: "optimizeLegibility" }}>Daily Recap</span>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: G3, fontSize: "18px", cursor: "pointer", padding: "8px", margin: "-8px" }}>×</button>
        </div>

        <div style={{ display: "flex", gap: "24px", marginBottom: "18px" }}>
          <div>
            <div style={sys("24px", WHITE, { fontWeight: 700, fontFamily: DISPLAY })}>{touched.length}</div>
            <div style={sys("9px", G3, { letterSpacing: "0.1em", marginTop: "4px" })}>TOUCHED</div>
          </div>
          <div>
            <div style={sys("24px", "#5a8a5a", { fontWeight: 700, fontFamily: DISPLAY })}>{shipped.length}</div>
            <div style={sys("9px", G3, { letterSpacing: "0.1em", marginTop: "4px" })}>SHIPPED</div>
          </div>
          <div>
            <div style={sys("24px", ACCENT, { fontWeight: 700, fontFamily: DISPLAY })}>{formatDuration(sessionMins)}</div>
            <div style={sys("9px", G3, { letterSpacing: "0.1em", marginTop: "4px" })}>SESSION</div>
          </div>
        </div>

        {touched.length > 0 && (
          <div style={{ borderTop: `1px solid ${G4}`, paddingTop: "12px" }}>
            {touched.map((p) => (
              <div key={p.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 0" }}>
                <span style={sys("9px", WHITE)}>{p.name}</span>
                <span style={sys("9px", statusColor(p.status))}>{p.status}</span>
              </div>
            ))}
          </div>
        )}

        {touched.length === 0 && (
          <div style={sys("9px", G3, { textAlign: "center", padding: "24px 0" })}>No projects touched today yet.</div>
        )}
      </div>
    </div>
  );
}

// ─── SHARE PANEL ────────────────────────────────────────────

function SharePanel({ viewers, onAdd, onRemove, onClose, newEmail, setNewEmail }) {
  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", zIndex: 200,
      display: "flex", alignItems: "center", justifyContent: "center", padding: "24px",
    }} onClick={onClose}>
      <div style={{
        background: G5, borderRadius: "4px", padding: "36px", maxWidth: "480px", width: "100%",
        border: `1px solid ${G4}`,
      }} onClick={e => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "18px" }}>
          <span style={{ fontFamily: DISPLAY, fontSize: "18px", color: WHITE, letterSpacing: "0.1em", textTransform: "uppercase", textRendering: "optimizeLegibility" }}>Share Board</span>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: G3, fontSize: "18px", cursor: "pointer", padding: "8px", margin: "-8px" }}>×</button>
        </div>

        {/* Add viewer */}
        <div style={{ display: "flex", gap: "8px", marginBottom: "18px" }}>
          <input value={newEmail} onChange={e => setNewEmail(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") onAdd(); }}
            placeholder="viewer@email.com" style={{ ...inp, flex: 1 }} />
          <button onClick={onAdd}
            style={{ ...inp, width: "auto", cursor: "pointer", color: ACCENT, padding: "8px 12px" }}>INVITE</button>
        </div>

        {/* Viewer list */}
        {viewers.length > 0 ? (
          <div style={{ borderTop: `1px solid ${G4}`, paddingTop: "12px" }}>
            {viewers.map(v => (
              <div key={v.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 0" }}>
                <div>
                  <div style={sys("9px", WHITE)}>{v.email}</div>
                  <div style={sys("9px", G4, { marginTop: "2px" })}>{v.lastSeen ? `Last seen: ${relTime(v.lastSeen)}` : "Never visited"}</div>
                </div>
                <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                  <button onClick={() => {
                    const url = `${window.location.origin}/join/${v.token}`;
                    navigator.clipboard.writeText(url).catch(() => {});
                  }}
                    style={{ ...sys("9px", G3), background: "transparent", border: `1px solid ${G4}`, padding: "4px 12px", cursor: "pointer", borderRadius: "4px" }}
                    onMouseEnter={e => { e.currentTarget.style.color = WHITE; }}
                    onMouseLeave={e => { e.currentTarget.style.color = G3; }}>
                    COPY LINK
                  </button>
                  <button onClick={() => onRemove(v.id)}
                    style={{ ...sys("9px", G3), background: "transparent", border: `1px solid ${G4}`, padding: "4px 12px", cursor: "pointer", borderRadius: "4px" }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = "#b04040"; e.currentTarget.style.color = "#b04040"; }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = G4; e.currentTarget.style.color = G3; }}>
                    REVOKE
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={sys("9px", G3, { textAlign: "center", padding: "18px 0" })}>No viewers yet. Invite someone to share your board.</div>
        )}
      </div>
    </div>
  );
}

// ─── MAIN ────────────────────────────────────────────────────

export default function Departures() {
  const [projects, setProjects] = useState([]);
  const [events, setEvents] = useState([]);
  const [openId, setOpenId] = useState(null);
  const [openEventId, setOpenEventId] = useState(null);
  const [filter, setFilter] = useState("TODAY");
  const [ready, setReady] = useState(false);
  const [interval, setInterval_] = useState(0.12);
  const [animKey, setAnimKey] = useState(0);
  const [showRecap, setShowRecap] = useState(false);
  const [sessionMins, setSessionMins] = useState(0);
  const [settings, setSettings] = useState({ zip: "", fontSize: "104", alignment: "left" });
  const [weather, setWeather] = useState(null);
  const [zipEditing, setZipEditing] = useState(false);
  const [zipDraft, setZipDraft] = useState("");
  const [role, setRole] = useState("owner");
  const [showShare, setShowShare] = useState(false);
  const [viewers, setViewers] = useState([]);
  const [newViewerEmail, setNewViewerEmail] = useState("");
  const prevFilter = useRef(filter);

  useEffect(() => {
    const l = document.createElement("link");
    l.href = "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&display=swap";
    l.rel = "stylesheet"; document.head.appendChild(l);

    const l2 = document.createElement("link");
    l2.href = "https://db.onlinewebfonts.com/c/3284c3a32cf946466fb963369b3c5b2d?family=Disket+Mono";
    l2.rel = "stylesheet"; document.head.appendChild(l2);

    return () => { document.head.removeChild(l); document.head.removeChild(l2); };
  }, []);

  useEffect(() => {
    const s = document.createElement("style");
    s.textContent = `
      body { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
      *:focus-visible { outline: 1px solid ${ACCENT}; outline-offset: 2px; }
      *:focus:not(:focus-visible) { outline: none; }
      ::-webkit-scrollbar { width: 6px; }
      ::-webkit-scrollbar-track { background: transparent; }
      ::-webkit-scrollbar-thumb { background: ${G5}; border-radius: 4px; }
      @keyframes arrive { 0% { opacity:0; transform:perspective(600px) rotateX(-50deg) translateY(-6px) } 70% { opacity:1; transform:perspective(600px) rotateX(2deg) } 100% { opacity:1; transform:perspective(600px) rotateX(0) } }
      .arrive { animation: arrive 0.36s cubic-bezier(0.22,1,0.36,1) both; transform-origin: top center; }
      @keyframes flapFlip { 0% { transform: perspective(200px) rotateX(-60deg); opacity:0.3; } 50% { transform: perspective(200px) rotateX(8deg); opacity:1; } 100% { transform: perspective(200px) rotateX(0); opacity:1; } }
    `;
    document.head.appendChild(s);
    return () => document.head.removeChild(s);
  }, []);

  // Load projects
  useEffect(() => {
    fetch('/api/projects')
      .then(r => r.json())
      .then(data => { setProjects(data); setReady(true); })
      .catch(() => setReady(true));
  }, []);

  // Load events from API
  useEffect(() => {
    fetch('/api/events')
      .then(r => r.json())
      .then(setEvents)
      .catch(() => {});
  }, []);

  // Load settings + weather
  useEffect(() => {
    fetch('/api/settings').then(r => r.json()).then(s => {
      setSettings(s);
      setZipDraft(s.zip || "");
      if (s.zip) fetchWeather(s.zip).then(setWeather);
    }).catch(() => {});
  }, []);

  // Session pulse
  useEffect(() => {
    const fetchSession = () => fetch('/api/session').then(r => r.json()).then(d => setSessionMins(d.elapsedMinutes)).catch(() => {});
    fetchSession();
    const t = setInterval(fetchSession, 60000);
    return () => clearInterval(t);
  }, []);

  // Load role
  useEffect(() => {
    fetch('/api/me').then(r => r.json()).then(d => setRole(d.role)).catch(() => {});
  }, []);

  const isViewer = role === "viewer";

  const loadViewers = () => fetch('/api/viewers').then(r => r.json()).then(setViewers).catch(() => {});

  const addViewer = () => {
    if (!newViewerEmail.trim() || !newViewerEmail.includes("@")) return;
    fetch('/api/viewers', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ email: newViewerEmail }) })
      .then(r => r.json())
      .then(() => { loadViewers(); setNewViewerEmail(""); });
  };

  const removeViewer = (id) => {
    fetch(`/api/viewers/${id}`, { method: 'DELETE' }).then(() => loadViewers());
  };

  useEffect(() => { if (prevFilter.current !== filter) { setAnimKey((k) => k + 1); prevFilter.current = filter; } }, [filter]);
  useEffect(() => { if (ready) setAnimKey((k) => k + 1); }, [ready]);

  // ─── Settings helpers ──────────────────────────────────────
  const saveSetting = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
    fetch('/api/settings', { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ [key]: value }) });
  };

  // ─── Project CRUD ──────────────────────────────────────────
  const add = () => {
    fetch('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'New Project', status: 'QUEUED', track: '03', domain: 'AI' }),
    })
      .then(r => r.json())
      .then(({ id }) => {
        fetch('/api/projects').then(r => r.json()).then(data => {
          setProjects(data);
          setOpenId(id);
        });
      });
  };
  const update = (p) => {
    setProjects(prev => prev.map(x => x.id === p.id ? { ...p, updatedAt: new Date().toISOString() } : x));
    fetch(`/api/projects/${p.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(p),
    });
  };
  const remove = (id) => {
    setProjects(prev => prev.filter(x => x.id !== id));
    if (openId === id) setOpenId(null);
    fetch(`/api/projects/${id}`, { method: 'DELETE' });
  };

  // ─── Event CRUD ────────────────────────────────────────────
  const updateEvent = (ev) => {
    setEvents(prev => prev.map(x => x.id === ev.id ? ev : x));
    fetch(`/api/events/${ev.id}`, { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(ev) });
  };
  const removeEvent = (id) => {
    setEvents(prev => prev.filter(x => x.id !== id));
    if (openEventId === id) setOpenEventId(null);
    fetch(`/api/events/${id}`, { method: 'DELETE' });
  };
  const addEvent = () => {
    fetch('/api/events', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ time: "12:00", endTime: "12:30", name: "New event" }) })
      .then(r => r.json())
      .then(({ id }) => { fetch('/api/events').then(r => r.json()).then(setEvents); setOpenEventId(id); });
  };

  // ─── Priority reorder ────────────────────────────────────
  const moveProject = (direction) => {
    if (!openId) return;
    // Work on the currently displayed list
    const displayList = isToday
      ? [...filtered, ...unscheduled]
      : filtered;
    const idx = displayList.findIndex(p => p.id === openId);
    if (idx === -1) return;
    const swapIdx = direction === "up" ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= displayList.length) return;
    const a = displayList[idx];
    const b = displayList[swapIdx];
    // Swap their tracks so sort order changes
    const trackA = a.track;
    const trackB = b.track;
    if (trackA !== trackB) {
      update({ ...a, track: trackB });
      update({ ...b, track: trackA });
    } else {
      // Same track: nudge the project to the adjacent track
      const allTracks = TRACKS;
      const trackIdx = allTracks.indexOf(a.track);
      const newTrack = direction === "up"
        ? allTracks[Math.max(0, trackIdx - 1)]
        : allTracks[Math.min(allTracks.length - 1, trackIdx + 1)];
      if (newTrack !== a.track) {
        update({ ...a, track: newTrack });
      }
    }
  };

  const isToday = filter === "TODAY";
  const flapSize = parseInt(settings.fontSize) || 104;
  const flapAlign = settings.alignment || "left";

  // Standard filters
  const filtered = isToday
    ? projects.filter((p) => p.status !== "SHIPPED" && p.todayTime)
    : projects
        .filter((p) => filter === "ALL" ? p.status !== "SHIPPED" : p.status === filter)
        .sort((a, b) => a.track.localeCompare(b.track) || STATUSES.indexOf(a.status) - STATUSES.indexOf(b.status));

  // TODAY view: build unified timeline
  const todayTimeline = (() => {
    if (!isToday) return [];
    const items = [];

    filtered.forEach((p) => {
      items.push({ type: "project", time: p.todayTime, data: p, sortKey: timeToMinutes(p.todayTime) });
    });

    events.forEach((ev) => {
      items.push({ type: "event", time: ev.time, data: ev, sortKey: timeToMinutes(ev.time) });
    });

    MOCK_EMAILS.forEach((em) => {
      items.push({ type: "email", time: em.time, data: em, sortKey: timeToMinutes(em.time) });
    });

    items.sort((a, b) => a.sortKey - b.sortKey);

    const nowMin = new Date().getHours() * 60 + new Date().getMinutes();
    let nowInserted = false;
    const result = [];
    for (const item of items) {
      if (!nowInserted && item.sortKey >= nowMin) {
        result.push({ type: "now", sortKey: nowMin });
        nowInserted = true;
      }
      result.push(item);
    }
    if (!nowInserted) result.push({ type: "now", sortKey: nowMin });

    return result;
  })();

  // Unscheduled active projects (TODAY view)
  const unscheduled = isToday
    ? projects.filter((p) => p.status !== "SHIPPED" && p.status !== "QUEUED" && !p.todayTime)
    : [];

  // Clock + session pulse
  const [now, setNow] = useState(new Date());
  useEffect(() => { const t = window.setInterval(() => setNow(new Date()), 1000); return () => window.clearInterval(t); }, []);
  const time = now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
  const date = now.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }).toUpperCase();
  // NEXT UP — highest scoring active project
  const nextUpId = (() => {
    const scorable = projects.filter((p) => p.status !== "SHIPPED" && p.status !== "QUEUED");
    if (!scorable.length) return null;
    return scorable.reduce((best, p) => scoreProject(p) > scoreProject(best) ? p : best, scorable[0]).id;
  })();

  const intervals = [0.06, 0.12, 0.25, 0.5, 1.0];
  const filters = ["ALL", "TODAY", "ACTIVE", "ROLLING", "BLOCKED", "QUEUED", "SHIPPED"];

  if (!ready) return (
    <div style={{ background: BG, color: G4, height: "100vh", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: DISPLAY, fontSize: "14px", letterSpacing: "0.2em", textRendering: "optimizeLegibility" }}>LOADING</div>
  );

  return (
    <div style={{ background: BG, minHeight: "100vh", fontFamily: MONO }}>

      {/* HEADER */}
      <div style={{ padding: "24px 24px 12px", borderBottom: `1px solid ${G4}` }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          {/* Left: title + date + pulse */}
          <div>
            <h1 style={{ fontFamily: DISPLAY, fontSize: "16px", fontWeight: 400, color: WHITE, letterSpacing: "0.1em", margin: 0, lineHeight: 1, textTransform: "uppercase", textRendering: "optimizeLegibility" }}>
              {isToday ? "Today" : "Departures"}
            </h1>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "4px" }}>
              <div style={sys("9px", G4, { letterSpacing: "0.12em" })}>
                {isToday ? date : "USD-COMPOSED PROJECT STATE"}
              </div>
              <div title={formatDuration(sessionMins)} style={{ width: "5px", height: "5px", borderRadius: "50%", background: sessionColor(sessionMins), transition: "background 0.3s ease", cursor: "default" }} />
            </div>
          </div>

          {/* Right: weather/zip + clock */}
          <div style={{ display: "flex", alignItems: "flex-start", gap: "18px" }}>
            {/* Weather / zip input */}
            <div style={{ textAlign: "right", minWidth: "80px" }}>
              {weather && !zipEditing ? (
                <div onClick={() => { setZipDraft(settings.zip); setZipEditing(true); }} style={{ cursor: "pointer" }}>
                  <div style={sys("9px", G2, { fontWeight: 600, textAlign: "right" })}>{weather.temp}° {weather.desc.toUpperCase()}</div>
                  <div style={sys("9px", G4, { marginTop: "2px", textAlign: "right" })}>{weather.city}</div>
                </div>
              ) : (
                <div>
                  <input
                    autoFocus
                    value={zipDraft}
                    onChange={e => setZipDraft(e.target.value.replace(/\D/g, "").slice(0, 5))}
                    onBlur={() => {
                      if (zipDraft.length === 5) {
                        saveSetting("zip", zipDraft);
                        fetchWeather(zipDraft).then(w => { if (w) { setWeather(w); setZipEditing(false); } });
                      }
                    }}
                    onKeyDown={e => {
                      if (e.key === "Enter" && zipDraft.length === 5) {
                        saveSetting("zip", zipDraft);
                        fetchWeather(zipDraft).then(w => { if (w) { setWeather(w); setZipEditing(false); } });
                      }
                      if (e.key === "Escape") setZipEditing(false);
                    }}
                    placeholder="ZIP"
                    style={{ fontFamily: MONO, fontSize: "10px", color: WHITE, background: G6, border: `1px solid ${G4}`, borderRadius: "4px", outline: "none", width: "64px", textAlign: "center", letterSpacing: "0.14em", padding: "6px 8px", boxSizing: "border-box" }}
                  />
                </div>
              )}
            </div>
            {/* Clock + interval */}
            <div style={{ textAlign: "right" }}>
              <div style={{ fontFamily: MONO, fontSize: "18px", fontWeight: 800, color: G2, letterSpacing: "0.06em", lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>{time}</div>
              <div style={{ display: "flex", gap: "0px", marginTop: "4px", justifyContent: "flex-end" }}>
                {intervals.map((v) => (
                  <button key={v} onClick={() => setInterval_(v)} style={{
                    background: "transparent", border: "none", fontFamily: MONO, fontSize: "6px",
                    color: interval === v ? G2 : G5, cursor: "pointer", padding: "4px 4px",
                    letterSpacing: "0", lineHeight: 1, transition: "color 0.12s",
                  }}>{v < 1 ? `.${String(v).split(".")[1]}` : "1s"}</button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* FILTERS */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 24px", borderBottom: `1px solid ${G4}` }}>
        <div style={{ display: "flex" }}>
          {filters.map((f) => (
            <button key={f} onClick={() => setFilter(f)} style={{
              background: "transparent", border: "none", fontFamily: MONO, fontSize: "11px",
              fontWeight: filter === f ? 700 : 400, color: filter === f ? WHITE : G4,
              letterSpacing: "0.1em", padding: "8px 12px", cursor: "pointer", transition: "color 0.12s",
            }}>{f}</button>
          ))}
        </div>
        {/* Font size + alignment controls */}
        <div style={{ display: "flex", alignItems: "center" }}>
          <div style={{ display: "flex", gap: "0px" }}>
            {FONT_SIZES.map(fs => (
              <button key={fs.label} onClick={() => saveSetting("fontSize", String(fs.value))} style={{
                background: "transparent", border: "none", fontFamily: MONO, fontSize: "11px",
                color: parseInt(settings.fontSize) === fs.value ? G1 : G3,
                cursor: "pointer", padding: "8px 8px", letterSpacing: "0.06em", transition: "color 0.12s",
              }}>{fs.label}</button>
            ))}
          </div>
          <div style={{ width: "1px", height: "12px", background: G4, marginLeft: "4px", marginRight: "4px" }} />
          <div style={{ display: "flex", gap: "0px" }}>
            {["left", "center", "right"].map(a => (
              <button key={a} onClick={() => saveSetting("alignment", a)} style={{
                background: "transparent", border: "none", fontFamily: MONO, fontSize: "11px",
                color: settings.alignment === a ? G1 : G3,
                cursor: "pointer", padding: "8px 8px", letterSpacing: "0.06em", transition: "color 0.12s",
              }}>{a === "left" ? "◁" : a === "center" ? "·" : "▷"}</button>
            ))}
          </div>
        </div>
      </div>

      {/* VIEWER BANNER */}
      {isViewer && (
        <div style={{ padding: "8px 24px", background: G6, borderBottom: `1px solid ${G4}`, textAlign: "center" }}>
          <span style={sys("9px", G3, { letterSpacing: "0.08em" })}>VIEWING · READ ONLY</span>
        </div>
      )}

      {/* BOARD */}
      <div style={{ perspective: "800px", display: "flex", flexDirection: "column", gap: "18px", padding: "18px 0" }}>

        {isToday ? (
          <>
            {todayTimeline.map((item, i) => {
              if (item.type === "now") return <NowLine key="now" />;
              if (item.type === "event") return (
                <div key={item.data.id} className="arrive" style={{ animationDelay: `${i * interval}s`, padding: "0 12px" }}>
                  <EventRow event={item.data} open={openEventId === item.data.id}
                    onToggle={() => setOpenEventId(openEventId === item.data.id ? null : item.data.id)}
                    onUpdate={updateEvent} onDelete={removeEvent} readOnly={isViewer} />
                </div>
              );
              if (item.type === "email") return (
                <div key={item.data.id} className="arrive" style={{ animationDelay: `${i * interval}s`, padding: "0 12px" }}>
                  <EmailRow email={item.data} />
                </div>
              );
              if (item.type === "project") return (
                <div key={`${item.data.id}-${animKey}`} className="arrive" style={{ animationDelay: `${i * interval}s`, padding: "0 12px" }}>
                  <ProjectRow project={item.data} onUpdate={update} onDelete={remove} open={openId === item.data.id}
                    onToggle={() => setOpenId(openId === item.data.id ? null : item.data.id)} showTime isNextUp={item.data.id === nextUpId}
                    flapSize={flapSize} flapAlign={flapAlign} readOnly={isViewer} />
                </div>
              );
              return null;
            })}

            {unscheduled.length > 0 && (
              <>
                <SectionLabel label="No time blocked" />
                {unscheduled.map((p, i) => (
                  <div key={`${p.id}-${animKey}`} className="arrive" style={{ animationDelay: `${(todayTimeline.length + i) * interval}s`, padding: "0 12px" }}>
                    <ProjectRow project={p} onUpdate={update} onDelete={remove} open={openId === p.id}
                      onToggle={() => setOpenId(openId === p.id ? null : p.id)} showTime={false} isNextUp={p.id === nextUpId}
                      flapSize={flapSize} flapAlign={flapAlign} readOnly={isViewer} />
                  </div>
                ))}
              </>
            )}
          </>
        ) : (
          <>
            {filtered.map((p, i) => (
              <div key={`${p.id}-${animKey}`} className="arrive" style={{ animationDelay: `${i * interval}s`, padding: "0 12px" }}>
                <ProjectRow project={p} onUpdate={update} onDelete={remove} open={openId === p.id}
                  onToggle={() => setOpenId(openId === p.id ? null : p.id)} showTime={false} isNextUp={p.id === nextUpId}
                  flapSize={flapSize} flapAlign={flapAlign} readOnly={isViewer} />
              </div>
            ))}
          </>
        )}

        {!isToday && filtered.length === 0 && (
          <div style={{ padding: "48px 36px", textAlign: "center" }}>
            <div style={{ fontFamily: DISPLAY, fontSize: "14px", color: G4, letterSpacing: "0.2em", textRendering: "optimizeLegibility" }}>{filter === "ALL" ? "NO ACTIVE DEPARTURES" : `NO ${filter} PROJECTS`}</div>
          </div>
        )}
      </div>

      {/* ACTIONS */}
      <div style={{ position: "fixed", bottom: "24px", right: "24px", display: "flex", gap: "8px", zIndex: 50 }}>
        {!isViewer && isToday && (
          <button onClick={addEvent} title="Add event" style={{
            width: "36px", height: "36px", borderRadius: "50%",
            background: G5, border: `1px solid ${G4}`,
            color: G3, fontFamily: MONO, fontSize: "9px", fontWeight: 700,
            cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
            transition: "all 0.15s", letterSpacing: "0.02em",
          }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = G2; e.currentTarget.style.color = G2; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = G4; e.currentTarget.style.color = G3; }}>
            EV+
          </button>
        )}
        {!isViewer && (
          <button onClick={() => { loadViewers(); setShowShare(true); }} title="Share board" style={{
            width: "44px", height: "44px", borderRadius: "50%",
            background: G5, border: `1px solid ${G4}`,
            color: G3, fontFamily: MONO, fontSize: "9px", fontWeight: 700,
            cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
            transition: "all 0.15s", letterSpacing: "0.02em",
          }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = G2; e.currentTarget.style.color = G2; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = G4; e.currentTarget.style.color = G3; }}>
            SHR
          </button>
        )}
        <button onClick={() => setShowRecap(true)} style={{
          width: "44px", height: "44px", borderRadius: "50%",
          background: G5, border: `1px solid ${G4}`,
          color: G3, fontFamily: MONO, fontSize: "9px", fontWeight: 700,
          cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
          transition: "all 0.15s", letterSpacing: "0.02em",
        }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = G2; e.currentTarget.style.color = G2; }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = G4; e.currentTarget.style.color = G3; }}>
          REC
        </button>
        {!isViewer && (
          <button onClick={() => moveProject("up")} title="Move up" style={{
            width: "44px", height: "44px", borderRadius: "50%",
            background: openId ? G5 : G5, border: openId ? `1px solid ${G4}` : "none",
            color: openId ? G2 : G4, fontFamily: MONO, fontSize: "14px", fontWeight: 400,
            cursor: openId ? "pointer" : "default", display: "flex", alignItems: "center", justifyContent: "center",
            transition: "all 0.15s", lineHeight: 1,
          }}
            onMouseEnter={(e) => { if (openId) { e.currentTarget.style.borderColor = G2; e.currentTarget.style.color = WHITE; } }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = openId ? G4 : "transparent"; e.currentTarget.style.color = openId ? G2 : G4; }}>▲</button>
        )}
        {!isViewer && (
          <button onClick={() => moveProject("down")} title="Move down" style={{
            width: "44px", height: "44px", borderRadius: "50%",
            background: openId ? G5 : G5, border: openId ? `1px solid ${G4}` : "none",
            color: openId ? G2 : G4, fontFamily: MONO, fontSize: "14px", fontWeight: 400,
            cursor: openId ? "pointer" : "default", display: "flex", alignItems: "center", justifyContent: "center",
            transition: "all 0.15s", lineHeight: 1,
          }}
            onMouseEnter={(e) => { if (openId) { e.currentTarget.style.borderColor = G2; e.currentTarget.style.color = WHITE; } }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = openId ? G4 : "transparent"; e.currentTarget.style.color = openId ? G2 : G4; }}>▼</button>
        )}
        {!isViewer && (
          <button onClick={() => openId && remove(openId)} style={{
            width: "44px", height: "44px", borderRadius: "50%",
            background: openId ? G4 : G5, border: "none",
            color: openId ? WHITE : G3, fontFamily: DISPLAY, fontSize: "22px", fontWeight: 300,
            cursor: openId ? "pointer" : "default", display: "flex", alignItems: "center", justifyContent: "center",
            transition: "all 0.15s", lineHeight: 1, paddingBottom: "2px",
          }}
            onMouseEnter={(e) => { if (openId) { e.currentTarget.style.background = "#b04040"; e.currentTarget.style.color = "#000"; } }}
            onMouseLeave={(e) => { e.currentTarget.style.background = openId ? G4 : G5; e.currentTarget.style.color = openId ? WHITE : G3; }}>−</button>
        )}
        {!isViewer && (
          <button onClick={add} style={{
            width: "44px", height: "44px", borderRadius: "50%",
            background: ACCENT, border: "none", color: "#000",
            fontFamily: DISPLAY, fontSize: "22px", fontWeight: 500, cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
            transition: "all 0.15s", lineHeight: 1, paddingBottom: "2px",
            boxShadow: `0 4px 18px ${ACCENT}33`,
          }}
            onMouseEnter={(e) => e.currentTarget.style.transform = "scale(1.06)"}
            onMouseLeave={(e) => e.currentTarget.style.transform = "scale(1)"}>+</button>
        )}
      </div>

      {/* RECAP MODAL */}
      {showRecap && <RecapPanel projects={projects} sessionMins={sessionMins} onClose={() => setShowRecap(false)} />}

      {/* SHARE MODAL */}
      {showShare && <SharePanel viewers={viewers} onAdd={addViewer} onRemove={removeViewer}
        onClose={() => setShowShare(false)} newEmail={newViewerEmail} setNewEmail={setNewViewerEmail} />}

      {/* FOOTER */}
      <div style={{ padding: "24px 24px 48px", textAlign: "center" }}>
        <span style={sys("9px", G5, { letterSpacing: "0.2em" })}>DEPARTURES 0.4 · USD-COMPOSED · SOLARI PROTOCOL</span>
      </div>
    </div>
  );
}
