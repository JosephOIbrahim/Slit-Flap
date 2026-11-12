import { DISPLAY, WHITE, WHISPER, RED, GREEN, G4, G5, sys, whisper, inp } from "../theme";
import { relTime, statusColor, formatDuration } from "../utils";

// ─── MODAL SHELL ─────────────────────────────────────────────

function Modal({ title, onClose, children }) {
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
          <span style={{ fontFamily: DISPLAY, fontSize: "18px", color: WHITE, letterSpacing: "0.1em", textTransform: "uppercase", textRendering: "optimizeLegibility" }}>{title}</span>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: WHISPER, fontSize: "18px", cursor: "pointer", padding: "8px", margin: "-8px" }}>×</button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ─── DAILY RECAP ─────────────────────────────────────────────

export function RecapPanel({ projects, sessionMins, onClose }) {
  const today = new Date().toDateString();
  const touched = projects.filter((p) => {
    if (!p.lastTouched) return false;
    return new Date(p.lastTouched).toDateString() === today;
  });
  const shipped = touched.filter((p) => p.status === "SHIPPED");

  return (
    <Modal title="Daily Recap" onClose={onClose}>
      <div style={{ display: "flex", gap: "24px", marginBottom: "18px" }}>
        <div>
          <div style={sys("24px", WHITE, { fontWeight: 700, fontFamily: DISPLAY })}>{touched.length}</div>
          <div style={whisper({ letterSpacing: "0.1em", marginTop: "4px" })}>TOUCHED</div>
        </div>
        <div>
          <div style={sys("24px", GREEN, { fontWeight: 700, fontFamily: DISPLAY })}>{shipped.length}</div>
          <div style={whisper({ letterSpacing: "0.1em", marginTop: "4px" })}>SHIPPED</div>
        </div>
        <div>
          <div style={sys("24px", WHITE, { fontWeight: 700, fontFamily: DISPLAY })}>{formatDuration(sessionMins)}</div>
          <div style={whisper({ letterSpacing: "0.1em", marginTop: "4px" })}>SESSION</div>
        </div>
      </div>

      {touched.length > 0 ? (
        <div style={{ borderTop: `1px solid ${G4}`, paddingTop: "12px" }}>
          {touched.map((p) => (
            <div key={p.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 0" }}>
              <span style={whisper({ color: WHITE })}>{p.name}</span>
              <span style={whisper({ color: statusColor(p.status) })}>{p.status}</span>
            </div>
          ))}
        </div>
      ) : (
        <div style={whisper({ textAlign: "center", padding: "24px 0" })}>No projects touched today yet.</div>
      )}
    </Modal>
  );
}

// ─── SHARE PANEL ────────────────────────────────────────────

export function SharePanel({ viewers, onAdd, onRemove, onClose, newEmail, setNewEmail }) {
  return (
    <Modal title="Share Board" onClose={onClose}>
      {/* Add viewer */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "18px" }}>
        <input value={newEmail} onChange={e => setNewEmail(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") onAdd(); }}
          placeholder="viewer@email.com" style={{ ...inp, flex: 1 }} />
        <button onClick={onAdd}
          style={{ ...inp, width: "auto", cursor: "pointer", color: WHITE, padding: "8px 12px" }}>INVITE</button>
      </div>

      {/* Viewer list */}
      {viewers.length > 0 ? (
        <div style={{ borderTop: `1px solid ${G4}`, paddingTop: "12px" }}>
          {viewers.map(v => (
            <div key={v.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 0" }}>
              <div>
                <div style={whisper({ color: WHITE })}>{v.email}</div>
                <div style={whisper({ marginTop: "2px" })}>{v.lastSeen ? `Last seen: ${relTime(v.lastSeen)}` : "Never visited"}</div>
              </div>
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <button onClick={() => {
                  const url = `${window.location.origin}/join/${v.token}`;
                  navigator.clipboard.writeText(url).catch(() => {});
                }}
                  style={{ ...whisper(), background: "transparent", border: `1px solid ${G4}`, padding: "4px 12px", cursor: "pointer", borderRadius: "4px" }}
                  onMouseEnter={e => { e.currentTarget.style.color = WHITE; }}
                  onMouseLeave={e => { e.currentTarget.style.color = WHISPER; }}>
                  COPY LINK
                </button>
                <button onClick={() => onRemove(v.id)}
                  style={{ ...whisper(), background: "transparent", border: `1px solid ${G4}`, padding: "4px 12px", cursor: "pointer", borderRadius: "4px" }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = RED; e.currentTarget.style.color = RED; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = G4; e.currentTarget.style.color = WHISPER; }}>
                  REVOKE
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={whisper({ textAlign: "center", padding: "18px 0" })}>No viewers yet. Invite someone to share your board.</div>
      )}
    </Modal>
  );
}
