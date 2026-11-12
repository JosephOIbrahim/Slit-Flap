import { useState, useEffect, useRef } from "react";

// ─────────────────────────────────────────────────────────────
// DEPARTURES v0.5 — the board.
//
// Design principles: earned space, shout/whisper, one grid,
// color as information, motion as punctuation, empty states
// designed, invisible details resolved.
//
// v0.5: modular frontend, flip-to-notes card backs, deadline
// departure language (DEPARTS 3D / DELAYED), single source of
// truth for theme + API access.
// ─────────────────────────────────────────────────────────────

import { ACCENT, WHITE, BG, RISK, DISPLAY, MONO, G1, G2, G3, G4, G5, G6, sys, FONT_SIZES } from "./theme";
import { api } from "./api";
import { scoreProject, sessionColor, formatDuration, timeToMinutes, fetchWeather } from "./utils";
import { ProjectCard } from "./components/ProjectCard";
import { EventRow, EmailRow, NowLine, SectionLabel } from "./components/Rows";
import { RecapPanel, SharePanel } from "./components/Modals";

// Mock emails (would come from Gmail MCP)
const MOCK_EMAILS = [
  { id: "em1", type: "email", time: "08:15", from: "Figma", subject: "New comment on Brand Refresh — color system", linkedProject: "brand-refresh" },
  { id: "em2", type: "email", time: "09:45", from: "Vercel", subject: "Deploy succeeded: portfolio site", linkedProject: "portfolio-site" },
  { id: "em3", type: "email", time: "12:20", from: "GitHub", subject: "New issue: render pipeline memory leak", linkedProject: "render-pipeline" },
];

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
  const [backup, setBackup] = useState({ failed: false, problem: null, last: null });
  const [version, setVersion] = useState("0.5");
  const [settings, setSettings] = useState({ zip: "", fontSize: "104", alignment: "left" });
  const [weather, setWeather] = useState(null);
  const [zipEditing, setZipEditing] = useState(false);
  const [zipDraft, setZipDraft] = useState("");
  const [role, setRole] = useState("owner");
  const [showShare, setShowShare] = useState(false);
  const [viewers, setViewers] = useState([]);
  const [newViewerEmail, setNewViewerEmail] = useState("");
  const [clockWrong, setClockWrong] = useState(false);
  const [reloadNotice, setReloadNotice] = useState(false);
  const prevFilter = useRef(filter);

  // ─── Reload machinery ──────────────────────────────────────
  // A restore (or a server restart) swaps the board under an open
  // tab. /api/session's startedAt changes, so the page refetches;
  // the server also refuses a save made from a page that is behind
  // (409). Edits that land mid-reload are held and replayed against
  // the refreshed board, never against the values that just left.
  const reloading = useRef(false);
  const reloadPromise = useRef(null);
  const pendingEdits = useRef([]);
  const reloadBase = useRef([]);
  const startedAt = useRef(null);
  const projectsRef = useRef([]);

  useEffect(() => { projectsRef.current = projects; }, [projects]);
  useEffect(() => {
    if (!reloadNotice) return;
    const t = window.setTimeout(() => setReloadNotice(false), 15000);
    return () => window.clearTimeout(t);
  }, [reloadNotice]);

  const holdEdit = (replay) => {
    if (!reloading.current) return false;
    pendingEdits.current.push(replay);
    return true;
  };

  const onSaveError = (err) => {
    if (!err || err.status !== 409) return;
    setReloadNotice(true);
    reloadBoard();
  };

  // Fields the page changed, so a held edit can be replayed onto the
  // refreshed row without carrying the values a restore just replaced.
  const changedFields = (before, after) => {
    const out = {};
    if (!before) return out;
    Object.keys(after).forEach((k) => {
      if (k === "updatedAt" || k === "history") return;
      if (JSON.stringify(after[k]) !== JSON.stringify(before[k])) out[k] = after[k];
    });
    return out;
  };

  const loadBoard = () => Promise.all([
    api.get('/projects').catch(() => null),
    api.get('/events').catch(() => null),
    api.get('/settings').catch(() => null),
  ]).then(([p, e, s]) => {
    if (p) setProjects(p);
    if (e) setEvents(e);
    if (s) {
      setSettings(s);
      setZipDraft(s.zip || "");
      if (s.zip) fetchWeather(s.zip).then(setWeather);
    }
    return p;
  });

  const reloadBoard = () => {
    if (reloadPromise.current) return reloadPromise.current;
    reloadBase.current = projectsRef.current;
    reloading.current = true;
    const run = loadBoard()
      .then((fresh) => {
        const held = pendingEdits.current;
        pendingEdits.current = [];
        held.forEach((replay) => { try { replay(fresh || []); } catch (_) { /* the board still wins */ } });
      })
      .catch(() => {})
      .finally(() => { reloading.current = false; reloadPromise.current = null; });
    reloadPromise.current = run;
    return run;
  };

  // ─── Fonts + global styles ─────────────────────────────────
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

  // ─── Initial loads ─────────────────────────────────────────
  useEffect(() => {
    api.get('/projects').then(data => { setProjects(data); setReady(true); }).catch(() => setReady(true));
    api.get('/events').then(setEvents).catch(() => {});
    api.get('/settings').then(s => {
      setSettings(s);
      setZipDraft(s.zip || "");
      if (s.zip) fetchWeather(s.zip).then(setWeather);
    }).catch(() => {});
    api.get('/me').then(d => setRole(d.role)).catch(() => {});
  }, []);

  // Session pulse. A changed startedAt means the server restarted or a
  // restore swapped the board: refetch everything the page is showing.
  useEffect(() => {
    const fetchSession = () => api.get('/session').then(d => {
      setSessionMins(d.elapsedMinutes);
      setBackup({ failed: !!d.backupFailed, problem: d.backupProblem || null, last: d.lastBackup || null });
      setClockWrong(!!d.clockWrong);
      if (d.version) setVersion(d.version);
      if (startedAt.current && d.startedAt && d.startedAt !== startedAt.current) reloadBoard();
      if (d.startedAt) startedAt.current = d.startedAt;
    }).catch(() => {});
    fetchSession();
    const t = setInterval(fetchSession, 60000);
    return () => clearInterval(t);
  }, []);

  const isViewer = role === "viewer";

  // ─── Viewers ───────────────────────────────────────────────
  const loadViewers = () => api.get('/viewers').then(setViewers).catch(() => {});
  const addViewer = () => {
    if (!newViewerEmail.trim() || !newViewerEmail.includes("@")) return;
    api.post('/viewers', { email: newViewerEmail })
      .then(() => { loadViewers(); setNewViewerEmail(""); })
      .catch(() => {});
  };
  const removeViewer = (id) => { api.del(`/viewers/${id}`).then(() => loadViewers()).catch(() => {}); };

  useEffect(() => { if (prevFilter.current !== filter) { setAnimKey((k) => k + 1); prevFilter.current = filter; } }, [filter]);
  useEffect(() => { if (ready) setAnimKey((k) => k + 1); }, [ready]);

  // ─── Settings ──────────────────────────────────────────────
  const saveSetting = (key, value) => {
    if (holdEdit(() => saveSetting(key, value))) return;
    setSettings(prev => ({ ...prev, [key]: value }));
    api.put('/settings', { [key]: value }).catch(() => {});
  };

  // ─── Project CRUD ──────────────────────────────────────────
  const add = () => {
    if (holdEdit(() => add())) return;
    api.post('/projects', { name: 'New Project', status: 'QUEUED', track: '03', domain: 'AI' })
      .then(({ id }) => {
        api.get('/projects').then(data => { setProjects(data); setOpenId(id); }).catch(() => {});
      })
      .catch(onSaveError);
  };
  const update = (p) => {
    if (holdEdit((fresh) => {
      // Replay only what the page changed, onto the refreshed row, so a
      // restore's values aren't overwritten by the ones it replaced.
      const now = fresh.find(x => x.id === p.id);
      if (!now) return;
      const before = reloadBase.current.find(x => x.id === p.id);
      const changed = changedFields(before, p);
      if (!Object.keys(changed).length) return;
      api.put(`/projects/${p.id}`, { ...changed, updatedAt: now.updatedAt }).catch(onSaveError);
    })) return;
    setProjects(prev => prev.map(x => x.id === p.id ? { ...p, updatedAt: new Date().toISOString() } : x));
    api.put(`/projects/${p.id}`, p).catch(onSaveError);
  };
  const remove = (id) => {
    if (holdEdit(() => remove(id))) return;
    setProjects(prev => prev.filter(x => x.id !== id));
    if (openId === id) setOpenId(null);
    api.del(`/projects/${id}`).catch(onSaveError);
  };

  // ─── Event CRUD ────────────────────────────────────────────
  const updateEvent = (ev) => {
    if (holdEdit(() => updateEvent(ev))) return;
    setEvents(prev => prev.map(x => x.id === ev.id ? ev : x));
    api.put(`/events/${ev.id}`, ev).catch(() => {});
  };
  const removeEvent = (id) => {
    if (holdEdit(() => removeEvent(id))) return;
    setEvents(prev => prev.filter(x => x.id !== id));
    if (openEventId === id) setOpenEventId(null);
    api.del(`/events/${id}`).catch(() => {});
  };
  const addEvent = () => {
    if (holdEdit(() => addEvent())) return;
    api.post('/events', { time: "12:00", endTime: "12:30", name: "New event" })
      .then(({ id }) => { api.get('/events').then(setEvents).catch(() => {}); setOpenEventId(id); })
      .catch(() => {});
  };

  // ─── Priority reorder ──────────────────────────────────────
  const moveProject = (direction, list) => {
    if (!openId) return;
    if (!list && holdEdit((fresh) => moveProject(direction, fresh))) return;
    const items = list || projects;
    const idx = items.findIndex(p => p.id === openId);
    if (idx === -1) return;
    const swapIdx = direction === "up" ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= items.length) return;
    const a = items[idx];
    const b = items[swapIdx];
    // Use index-based ordering if sortOrders are equal or both 0
    const orderA = (a.sortOrder !== b.sortOrder) ? a.sortOrder : idx;
    const orderB = (a.sortOrder !== b.sortOrder) ? b.sortOrder : swapIdx;
    // Optimistic: swap in local state immediately
    const newProjects = [...items];
    newProjects[idx] = { ...b, sortOrder: orderA };
    newProjects[swapIdx] = { ...a, sortOrder: orderB };
    setProjects(newProjects);
    // Persist both
    api.put(`/projects/${a.id}`, { sortOrder: orderB }).catch(onSaveError);
    api.put(`/projects/${b.id}`, { sortOrder: orderA }).catch(onSaveError);
  };

  const isToday = filter === "TODAY";
  const flapSize = parseInt(settings.fontSize) || 104;
  const flapAlign = settings.alignment || "left";

  // Standard filters
  const filtered = isToday
    ? projects.filter((p) => p.status !== "SHIPPED" && p.todayTime)
    : projects.filter((p) => filter === "ALL" ? p.status !== "SHIPPED" : p.status === filter);

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

  const cardProps = (p) => ({
    project: p, onUpdate: update, onDelete: remove,
    open: openId === p.id,
    onToggle: () => setOpenId(openId === p.id ? null : p.id),
    isNextUp: p.id === nextUpId,
    flapSize, flapAlign, readOnly: isViewer,
  });

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
            {reloadNotice && (
              <div
                role="status"
                title="The board was changed on the server since this page loaded (for example by a restore), so this page reloaded the projects to match. Edits held during the reload were re-applied to the board as it is now."
                style={sys("9px", G3, { letterSpacing: "0.12em", marginTop: "4px", whiteSpace: "nowrap", cursor: "default" })}
              >
                BOARD RELOADED · THIS PAGE WAS BEHIND
              </div>
            )}
            {backup.failed && (
              <div
                role="status"
                title={(backup.problem === "damaged"
                  ? "Today's backup couldn't be verified, and the board itself may be damaged. New work may not be recoverable. "
                    + (backup.last ? `Newest good backup: ${backup.last}. ` : "")
                    + "Run: departures restore  (to see the backups)."
                  : "Today's backup didn't work. Your board still saves as normal, and the backup is tried again every 30 minutes. "
                    + (backup.last ? `Newest good backup: ${backup.last}. ` : "")
                    + "The reason is in the board's window, or in launcher.log in the .departures folder.")}
                style={sys("9px", RISK, { letterSpacing: "0.12em", marginTop: "4px", whiteSpace: "nowrap", cursor: "default" })}
              >
                {backup.problem === "damaged" ? "BOARD MAY BE DAMAGED" : "BACKUP FAILED"}
              </div>
            )}
            {clockWrong && (
              <div
                role="status"
                title="The PC clock is behind the newest backup, so backups are kept separately and nothing is pruned until the clock is right. Set the clock forward to let old backups be cleaned up again."
                style={sys("9px", RISK, { letterSpacing: "0.12em", marginTop: "4px", whiteSpace: "nowrap", cursor: "default" })}
              >
                PC CLOCK IS BEHIND · BACKUPS KEPT SEPARATELY
              </div>
            )}
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
                  <ProjectCard {...cardProps(item.data)} showTime />
                </div>
              );
              return null;
            })}

            {unscheduled.length > 0 && (
              <>
                <SectionLabel label="No time blocked" />
                {unscheduled.map((p, i) => (
                  <div key={`${p.id}-${animKey}`} className="arrive" style={{ animationDelay: `${(todayTimeline.length + i) * interval}s`, padding: "0 12px" }}>
                    <ProjectCard {...cardProps(p)} showTime={false} />
                  </div>
                ))}
              </>
            )}
          </>
        ) : (
          <>
            {filtered.map((p, i) => (
              <div key={`${p.id}-${animKey}`} className="arrive" style={{ animationDelay: `${i * interval}s`, padding: "0 12px" }}>
                <ProjectCard {...cardProps(p)} showTime={false} />
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
            background: G5, border: openId ? `1px solid ${G4}` : "none",
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
            background: G5, border: openId ? `1px solid ${G4}` : "none",
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
        <span style={sys("9px", G5, { letterSpacing: "0.2em" })}>DEPARTURES {version} · USD-COMPOSED · SOLARI PROTOCOL</span>
      </div>
    </div>
  );
}
