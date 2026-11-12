import { useState, useEffect } from "react";
import { WHITE, WHISPER, HOVER, RISK, G4, G5, G6, whisper, sentence, inp } from "../theme";

// ─── EVENT EDIT PANEL ────────────────────────────────────────

function EventEditPanel({ event, projects, onUpdate, onDelete }) {
  const [draft, setDraft] = useState({
    time: event.time || "",
    endTime: event.endTime || event.end || "",
    date: event.date || "",
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
      <div className="event-edit-actions" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px" }}>
        <div className="event-edit-fields" style={{ display: "flex", gap: "8px", flex: 1, minWidth: 0 }}>
          <input type="date" value={draft.date} onChange={e => d("date", e.target.value)} onBlur={save}
            title="The day this event happens" style={{ ...inp, width: "140px" }} />
          <select value={draft.linkedProject} onChange={e => { d("linkedProject", e.target.value); }}
            onBlur={save} style={{ ...inp, width: "200px" }}>
            <option value="">— no project —</option>
            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
        <button onClick={() => onDelete(event.id)}
          style={{ ...whisper(), background: "transparent", border: `1px solid ${G4}`, padding: "8px 12px", cursor: "pointer", borderRadius: "4px" }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = RISK; e.currentTarget.style.color = RISK; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = G4; e.currentTarget.style.color = WHISPER; }}>
          DELETE
        </button>
      </div>
    </div>
  );
}

// ─── EVENT ROW (TIER 2 — SPEAK) ─────────────────────────────

export function EventRow({ event, projects = [], open, onToggle, onUpdate, onDelete, readOnly }) {
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
        onMouseEnter={(e) => { e.currentTarget.parentElement.style.background = HOVER; }}
        onMouseLeave={(e) => { e.currentTarget.parentElement.style.background = G5; }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", flex: 1, minWidth: 0 }}>
          <span style={whisper({ color: WHITE, fontWeight: 600, minWidth: "42px" })}>{event.time}</span>
          <span style={sentence({ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{event.name}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", flexShrink: 0 }}>
          {linked && <span style={whisper({ letterSpacing: "0.08em" })}>→ {linked}</span>}
          <span style={whisper({ letterSpacing: "0.06em" })}>{event.endTime || event.end}</span>
        </div>
      </div>
      {open && !readOnly && <EventEditPanel event={event} projects={projects} onUpdate={onUpdate} onDelete={onDelete} />}
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
        <span style={whisper({ minWidth: "42px" })}>{email.time}</span>
        <span style={whisper({ fontWeight: 600 })}>{email.from}</span>
        <span style={whisper({ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 })}>{email.subject}</span>
      </div>
      {email.linkedProject && <span style={whisper({ letterSpacing: "0.06em" })}>→ {email.linkedProject}</span>}
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
      <span style={whisper({ color: WHITE, fontWeight: 700 })}>NOW {h}:{m}</span>
      <div style={{ flex: 1, height: "1px", background: `linear-gradient(to right, ${WHITE}, transparent)` }} />
    </div>
  );
}

// ─── SECTION LABEL ───────────────────────────────────────────

export function SectionLabel({ label }) {
  return (
    <div style={{ padding: "12px 36px 4px" }}>
      <span style={whisper({ letterSpacing: "0.14em", textTransform: "uppercase" })}>{label}</span>
    </div>
  );
}
