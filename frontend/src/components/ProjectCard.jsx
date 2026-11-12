import { useState, useEffect, useRef } from "react";
import { ACCENT, WHITE, WHISPER, HOVER, NOTES_BG, RISK, MONO, G1, G4, G5, G6, sys, whisper, inp, STATUSES, TRACKS, DOMAINS, SWATCHES } from "../theme";
import { relTime, statusColor, departure, localDate } from "../utils";
import { SplitFlapName } from "./SplitFlap";
import { api } from "../api";
import { canSaveNotes, createNotesSaveQueue, plainTextFrom } from "../notesEdit";

// ─── PROGRESS (mile markers) ─────────────────────────────────

function Progress({ mile, of: total }) {
  if (!total) return null;
  const pct = Math.round((mile / total) * 100);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <div style={{ width: "48px", height: "2px", background: G4, borderRadius: "4px", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: pct >= 100 ? "#5a8a5a" : WHITE, transition: "width 0.48s ease" }} />
      </div>
      <span style={whisper()}>{mile}/{total}</span>
    </div>
  );
}

// ─── EDIT PANEL ──────────────────────────────────────────────

function EditPanel({ project, onUpdate, onDelete, onRestore }) {
  const u = (k, v) => onUpdate({ ...project, [k]: v });
  return (
    <div style={{ padding: "18px 24px 18px", borderTop: `1px solid ${G4}`, background: G6 }} onClick={(e) => e.stopPropagation()}>
      <div className="edit-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "8px" }}>
        <input value={project.name} onChange={(e) => u("name", e.target.value)} placeholder="PROJECT" style={inp} />
        <input value={project.next} onChange={(e) => u("next", e.target.value)} placeholder="NEXT ACTION" style={inp} />
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
        <span style={whisper({ letterSpacing: "0.1em" })}>TIME TODAY</span>
        <input type="time" value={project.todayTime || ""}
          onChange={(e) => {
            const time = e.target.value;
            onUpdate({ ...project, todayTime: time, todayDate: time ? localDate() : "" });
          }}
          style={{ ...inp, width: "120px" }} />
        {project.todayTime && project.todayDate && project.todayDate !== localDate() && (
          <button onClick={() => onUpdate({ ...project, todayTime: "", todayDate: "" })}
            title="This block was for another day"
            style={{ ...whisper(), background: "transparent", border: `1px solid ${G4}`,
                     padding: "6px 8px", borderRadius: "4px", cursor: "pointer" }}>
            {project.todayDate} · CLEAR
          </button>
        )}
      </div>
      <div className="edit-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "8px", marginBottom: "12px" }}>
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
        <span style={whisper({ letterSpacing: "0.1em", marginRight: "8px" })}>BG</span>
        {SWATCHES.map((c, i) => (
          <button key={i} onClick={() => u("bgColor", c)} style={{
            width: "18px", height: "18px", borderRadius: "4px",
            border: project.bgColor === c ? `1px solid ${WHITE}` : c ? `1px solid ${G4}` : `1px dashed ${G4}`,
            background: c || "transparent", cursor: "pointer", padding: 0,
          }} />
        ))}
        <input type="color" value={project.bgColor || "#191919"} onChange={(e) => u("bgColor", e.target.value)}
          style={{ width: "18px", height: "18px", border: "none", background: "none", cursor: "pointer", padding: 0, marginLeft: "4px" }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={whisper()}>/{project.id} · {project.history.length} transitions</span>
        <button onClick={() => (project.archivedAt ? onRestore(project.id) : onDelete(project.id))}
          style={{ ...whisper(), background: "transparent", border: `1px solid ${G4}`, padding: "8px 12px", cursor: "pointer", borderRadius: "4px" }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = project.archivedAt ? WHITE : RISK; e.currentTarget.style.color = project.archivedAt ? WHITE : RISK; }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = G4; e.currentTarget.style.color = WHISPER; }}>
          {project.archivedAt ? "RESTORE" : "ARCHIVE"}
        </button>
      </div>
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
            style={{ ...inp, width: "auto", cursor: "pointer", color: WHITE, padding: "8px 12px" }}>+</button>
        </div>
      )}
      {log.length > 0 && (
        <div style={{ maxHeight: "120px", overflowY: "auto" }}>
          {[...log].reverse().slice(0, 8).map((entry, i) => (
            <div key={i} style={{ display: "flex", gap: "8px", padding: "4px 0" }}>
              <span style={whisper({ minWidth: "36px", flexShrink: 0 })}>{relTime(entry.at)}</span>
              <span style={whisper()}>{entry.text}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── NOTES BACK (flip side of the card) ──────────────────────

function NotesBack({ project, active, onFlip, readOnly }) {
  const ref = useRef(null);
  const loadedOk = useRef(false);
  const timer = useRef(null);
  const stamp = useRef(null);       // the note version the editor loaded
  const noticeTimer = useRef(null);
  const saveRef = useRef(null);
  const [savedAt, setSavedAt] = useState(null);
  const [stale, setStale] = useState(false);
  const [loadState, setLoadState] = useState("loading");  // loading | ready | error

  const loadNotes = () => {
    setLoadState("loading");
    return api.get(`/projects/${project.id}/notes`).then(n => {
      if (ref.current) ref.current.innerHTML = n.content || "";
      stamp.current = n.updatedAt || null;
      if (n.updatedAt) setSavedAt(n.updatedAt);
      loadedOk.current = true;
      setLoadState("ready");
    }).catch(() => setLoadState("error"));  // never leave an empty editor able to save
  };

  // Lazy-load the first time the card flips; a failed load retries next time.
  useEffect(() => {
    if (active && !loadedOk.current) loadNotes();
  }, [active, project.id]);

  const saveQueue = useRef(null);
  if (!saveQueue.current) {
    saveQueue.current = createNotesSaveQueue({
      getDraft: () => ref.current ? ref.current.innerHTML : "",
      getNote: () => api.get(`/projects/${project.id}/notes`),
      putNote: (content, keepalive) => {
        const body = { content, updatedAt: stamp.current };
        return keepalive
          ? api.putKeepalive(`/projects/${project.id}/notes`, body)
          : api.put(`/projects/${project.id}/notes`, body);
      },
      onVersion: (value) => { stamp.current = value; },
      onSaved: (n) => { if (n && n.updatedAt) setSavedAt(n.updatedAt); },
      onConflict: () => {
        setStale(true);
        clearTimeout(noticeTimer.current);
        noticeTimer.current = setTimeout(() => setStale(false), 15000);
      },
    });
  }

  const save = ({ keepalive = false } = {}) => {
    if (!canSaveNotes(loadState, readOnly) || !ref.current) return;
    saveQueue.current.save(ref.current.innerHTML, { keepalive });
  };
  saveRef.current = save;

  // A thought typed in the last second before the tab hides must still go.
  useEffect(() => {
    const flush = () => {
      if (!timer.current) return;
      clearTimeout(timer.current);
      timer.current = null;
      if (saveRef.current) saveRef.current({ keepalive: true });
    };
    const onVisibility = () => { if (document.visibilityState === "hidden") flush(); };
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pagehide", flush);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pagehide", flush);
      clearTimeout(timer.current);
      clearTimeout(noticeTimer.current);
      flush();
    };
  }, []);

  const onInput = () => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => { timer.current = null; saveRef.current?.(); }, 1000);
  };

  const onPaste = (e) => {
    e.preventDefault();
    const text = plainTextFrom(e.clipboardData || window.clipboardData);
    document.execCommand("insertText", false, text);
    onInput();
  };

  return (
    <div onClick={(e) => e.stopPropagation()} style={{
      position: "absolute", inset: 0,
      transform: "rotateY(180deg)",
      backfaceVisibility: "hidden", WebkitBackfaceVisibility: "hidden",
      background: NOTES_BG, borderRadius: "4px",
      padding: "18px 24px", boxSizing: "border-box",
      display: "flex", flexDirection: "column", gap: "8px",
      overflow: "hidden", cursor: "default",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={whisper({ letterSpacing: "0.1em", textTransform: "uppercase" })}>{project.name} · NOTES</span>
        <button onClick={onFlip} title="Back to board" style={{
          background: "transparent", border: "none", fontFamily: MONO, fontSize: "11px",
          color: WHISPER, letterSpacing: "0.08em", cursor: "pointer", padding: "8px 4px", margin: "-8px -4px",
        }}
          onMouseEnter={(e) => { e.currentTarget.style.color = WHITE; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = WHISPER; }}>
          ↩ BOARD
        </button>
      </div>
      {stale && (
        <span role="status" style={whisper({ color: RISK, letterSpacing: "0.1em" })}>
          NOTE CHANGED ELSEWHERE · YOUR DRAFT IS KEPT
        </span>
      )}
      <div ref={ref} contentEditable={!readOnly && loadState === "ready"} suppressContentEditableWarning
        onInput={onInput} onBlur={() => save()} onPaste={onPaste}
        style={{
          flex: 1, overflowY: "auto", outline: "none",
          fontFamily: MONO, fontSize: "12px", color: G1,
          lineHeight: 1.7, letterSpacing: "0.02em", caretColor: WHITE,
        }} />
      {loadState === "error" ? (
        <button onClick={loadNotes} style={{
          ...whisper({ color: WHITE }), background: "transparent", border: `1px solid ${G4}`,
          padding: "6px 8px", borderRadius: "4px", cursor: "pointer", alignSelf: "flex-start",
          letterSpacing: "0.1em",
        }}>NOTES UNAVAILABLE · RETRY</button>
      ) : (
        <span style={whisper()}>
          {readOnly ? "READ ONLY"
            : loadState === "loading" ? "LOADING NOTES…"
            : savedAt ? `SAVED ${relTime(savedAt).toUpperCase()}`
            : "AUTO-SAVES · CTRL+B BOLD · CTRL+I ITALIC"}
        </span>
      )}
    </div>
  );
}

// ─── PROJECT CARD (TIER 1 — SHOUT) ───────────────────────────

export function ProjectCard({ project, onUpdate, onLog, onDelete, onRestore, open, onToggle, showTime, isNextUp, flapSize, flapAlign, readOnly }) {
  const shipped = project.status === "SHIPPED";
  const [flipping, setFlipping] = useState(false);
  const [flipped, setFlipped] = useState(false);
  const dep = departure(project);

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
    api.post(`/projects/${project.id}/logs`, { text }).then(entry => onLog(project.id, entry));
  };

  return (
    <div style={{ perspective: "1200px", position: "relative", zIndex: 1, transition: "transform 0.28s cubic-bezier(0.22, 1, 0.36, 1)" }}
      onMouseEnter={(e) => { const el = e.currentTarget; if (!shipped && !flipped) { el.style.transform = "scale(1.005) translateY(-2px)"; el.style.zIndex = "10"; } }}
      onMouseLeave={(e) => { const el = e.currentTarget; el.style.transform = "scale(1) translateY(0)"; el.style.zIndex = "1"; }}>
      <div style={{
        position: "relative", transformStyle: "preserve-3d",
        transition: "transform 0.6s cubic-bezier(0.22, 1, 0.36, 1)",
        transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)",
      }}>
        {/* FRONT */}
        <div style={{
          background: project.bgColor || G5, borderRadius: "4px",
          cursor: "pointer", overflow: "hidden",
          backfaceVisibility: "hidden", WebkitBackfaceVisibility: "hidden",
          borderLeft: isNextUp ? `3px solid ${ACCENT}` : "3px solid transparent",
          transition: "background 0.28s, box-shadow 0.28s",
        }}
          onClick={handleToggle}
          onMouseEnter={(e) => { const el = e.currentTarget; if (!shipped) { el.style.boxShadow = `0 4px 20px rgba(0,0,0,0.5), 0 0 0 1px ${G4}`; el.style.background = project.bgColor || HOVER; } }}
          onMouseLeave={(e) => { const el = e.currentTarget; el.style.boxShadow = "none"; el.style.background = project.bgColor || G5; }}>

          <div style={{
            padding: "18px 24px", minHeight: "180px", display: "flex", flexDirection: "column",
            justifyContent: "space-between", opacity: shipped ? 0.35 : 1, transition: "opacity 0.24s",
          }}>
            {/* Top whisper */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px" }}>
              <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: "6px 12px" }}>
                {isNextUp && (
                  <span style={sys("11px", ACCENT, { fontWeight: 700, letterSpacing: "0.14em" })}>NEXT UP</span>
                )}
                {showTime && project.todayTime ? (
                  <span style={whisper({ color: WHITE, fontWeight: 600 })}>{project.todayTime}</span>
                ) : (
                  <span style={whisper()}>{project.track}</span>
                )}
                <span style={whisper({ letterSpacing: "0.08em" })}>{project.domain}</span>
                <span style={whisper()}>{relTime(project.lastTouched)}</span>
                {dep && <span style={whisper({ color: dep.color, fontWeight: 600, letterSpacing: "0.08em" })}>{dep.label}</span>}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <button onClick={(e) => { e.stopPropagation(); setFlipped(true); }} title="Flip to notes" style={{
                  background: "transparent", border: "none", fontFamily: MONO, fontSize: "11px",
                  color: WHISPER, cursor: "pointer", padding: "8px 4px", margin: "-8px -4px",
                  transition: "color 0.12s", lineHeight: 1,
                }}
                  onMouseEnter={(e) => { e.currentTarget.style.color = WHITE; }}
                  onMouseLeave={(e) => { e.currentTarget.style.color = WHISPER; }}>
                  ↻
                </button>
                <button onClick={cycleStatus} style={{
                  background: "transparent", border: "none", fontFamily: MONO, fontSize: "11px", fontWeight: 600,
                  color: statusColor(project.status), letterSpacing: "0.1em", cursor: readOnly ? "default" : "pointer",
                  padding: "8px 4px", margin: "-8px -4px",
                }}>{project.status}</button>
              </div>
            </div>
            {/* Name shout — split flap display */}
            <div style={{ padding: "4px 0" }}>
              <SplitFlapName text={project.name} shipped={shipped} flipping={flipping} size={flapSize || 104} align={flapAlign || "left"} />
            </div>
            {/* Bottom: the next action is the sentence tier */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", minHeight: "12px", gap: "12px" }}>
              {project.next ? <span style={{
                fontFamily: MONO, fontSize: isNextUp ? "15px" : "14px", color: WHITE,
                letterSpacing: "0.02em", lineHeight: 1.5,
                flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
              }}>{project.next}</span> : <span />}
              {project.of > 0 && <Progress mile={project.mile} of={project.of} />}
            </div>
          </div>

          {/* Edit panel + log */}
          {open && (
            <>
              {!readOnly && <EditPanel project={project} onUpdate={onUpdate} onDelete={onDelete} onRestore={onRestore} />}
              <LogPanel log={project.log || []} onAdd={addLogEntry} readOnly={readOnly} />
            </>
          )}
        </div>

        {/* BACK — notes */}
        <NotesBack project={project} active={flipped} onFlip={() => setFlipped(false)} readOnly={readOnly} />
      </div>
    </div>
  );
}
