import { useState, useEffect } from "react";
import { ACCENT, MONO, RED, G1, G2, G3, G4, G5, G6, sys, inp } from "../theme";

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
          onMouseEnter={e => { e.currentTarget.style.borderColor = RED; e.currentTarget.style.color = RED; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = G4; e.currentTarget.style.color = G3; }}>
          DELETE
        </button>
      </div>
    </div>
  );
}

// ─── EVENT ROW (TIER 2 — SPEAK) ─────────────────────────────

export function EventRow({ event, open, onToggle, onUpdate, onDelete, readOnly }) {
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

export function EmailRow({ email }) {
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

export function NowLine() {
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

export function SectionLabel({ label }) {
  return (
    <div style={{ padding: "12px 36px 4px" }}>
      <span style={sys("9px", G4, { letterSpacing: "0.14em", textTransform: "uppercase" })}>{label}</span>
    </div>
  );
}
