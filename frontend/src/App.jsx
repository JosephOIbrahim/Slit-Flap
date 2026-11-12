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

import { ACCENT, WHITE, WHISPER, BG, RED, RISK, DISPLAY, MONO, G2, G3, G4, G5, G6, sys, whisper, sentence, FONT_SIZES } from "./theme";
import { api, saveState, startSaveQueue } from "./api";
import { changedFields, flushPendingSaves } from "./projectFields";
import { isPhoneWidth, flapSizeFor } from "./layout";
import { sessionColor, formatDuration, timeToMinutes, fetchWeather, localDate, nextHalfHour, FILTERS, nextUpProject, startHereText, filterCounts, visibleProjects, groupByTrack } from "./utils";
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
  const [archivedProjects, setArchivedProjects] = useState([]);
  const [undo, setUndo] = useState(null);  // {id, name} while the 5s undo is offered
  const [unsaved, setUnsaved] = useState(0);
  const undoTimer = useRef(null);
  const saveStamps = useRef(new Map());   // project id -> updatedAt the server last gave us
  const pendingSaves = useRef(new Map()); // id -> {patch, timer}
  const saveChains = useRef(new Map());   // id -> promise, so saves land in order
  const [settings, setSettings] = useState({ zip: "", fontSize: "104", alignment: "left" });
  const [weather, setWeather] = useState(null);
  const [zipEditing, setZipEditing] = useState(false);
  const [zipDraft, setZipDraft] = useState("");
  const [role, setRole] = useState("owner");
  const [showShare, setShowShare] = useState(false);
  const [viewers, setViewers] = useState([]);
  const [newViewerEmail, setNewViewerEmail] = useState("");
  const [clockWrong, setClockWrong] = useState(false);
  const [showDisplay, setShowDisplay] = useState(false);
  const [vw, setVw] = useState(() => (typeof window === "undefined" ? 1280 : window.innerWidth));
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

  useEffect(() => {
    const onResize = () => setVw(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  const isPhone = isPhoneWidth(vw);

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

  const loadBoard = () => Promise.all([
    api.get('/projects').catch(() => null),
    api.get('/events').catch(() => null),
    api.get('/settings').catch(() => null),
    api.get('/projects?archived=1').catch(() => null),
  ]).then(([p, e, s, a]) => {
    if (p) setProjects(p);
    if (e) setEvents(e);
    if (a) setArchivedProjects(a);
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
    // JetBrains Mono is bundled and declared in index.html. Disket Mono stays
    // on its licensed CDN: its EULA allows web use but not redistribution.
    const l2 = document.createElement("link");
    l2.href = "https://db.onlinewebfonts.com/c/3284c3a32cf946466fb963369b3c5b2d?family=Disket+Mono";
    l2.rel = "stylesheet"; document.head.appendChild(l2);

    return () => { document.head.removeChild(l2); };
  }, []);

  useEffect(() => {
    const s = document.createElement("style");
    s.textContent = `
      body { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
      *:focus-visible { outline: 1px solid ${WHITE}; outline-offset: 2px; }
      *:focus:not(:focus-visible) { outline: none; }
      ::-webkit-scrollbar { width: 6px; }
      ::-webkit-scrollbar-track { background: transparent; }
      ::-webkit-scrollbar-thumb { background: ${G5}; border-radius: 4px; }
      @keyframes arrive { 0% { opacity:0; transform:perspective(600px) rotateX(-50deg) translateY(-6px) } 70% { opacity:1; transform:perspective(600px) rotateX(2deg) } 100% { opacity:1; transform:perspective(600px) rotateX(0) } }
      .arrive { animation: arrive 0.36s cubic-bezier(0.22,1,0.36,1) both; transform-origin: top center; }
      @keyframes flapFlip { 0% { transform: perspective(200px) rotateX(-60deg); opacity:0.3; } 50% { transform: perspective(200px) rotateX(8deg); opacity:1; } 100% { transform: perspective(200px) rotateX(0); opacity:1; } }
      @media (max-width: 600px) {
        .board { padding-bottom: 68px; }
        .filters-bar { flex-wrap: wrap !important; justify-content: flex-start !important; padding: 8px 12px !important; }
        .filter-row { width: 100%; overflow-x: auto; white-space: nowrap; -webkit-overflow-scrolling: touch; scrollbar-width: none; }
        .filter-row::-webkit-scrollbar { display: none; }
        .actions { left: 0 !important; right: 0 !important; bottom: 0 !important; padding: 8px 10px !important; gap: 4px !important; background: #111 !important; border-top: 1px solid #2a2a2a !important; justify-content: space-between !important; }
        .actions button { width: auto !important; height: 44px !important; border-radius: 4px !important; padding: 0 8px !important; font-size: 10px !important; letter-spacing: 0.08em !important; }
        .edit-grid { grid-template-columns: 1fr !important; }
        .display-menu { left: 0 !important; right: auto !important; }
      }
    `;
    document.head.appendChild(s);
    return () => document.head.removeChild(s);
  }, []);

  // ─── Initial loads ─────────────────────────────────────────
  useEffect(() => {
    api.get('/projects').then(data => { setProjects(data); setReady(true); }).catch(() => setReady(true));
    api.get('/projects?archived=1').then(setArchivedProjects).catch(() => {});
    api.get('/events').then(setEvents).catch(() => {});
    api.get('/settings').then(s => {
      setSettings(s);
      setZipDraft(s.zip || "");
      if (s.zip) fetchWeather(s.zip).then(setWeather);
    }).catch(() => {});
    api.get('/me').then(d => setRole(d.role)).catch(() => {});
  }, []);

  useEffect(() => {
    projects.forEach((p) => saveStamps.current.set(p.id, p.updatedAt));
    archivedProjects.forEach((p) => saveStamps.current.set(p.id, p.updatedAt));
  }, [projects, archivedProjects]);

  // Unsaved work: writes that failed for a retryable reason sit in the
  // queue and are retried until they land. One amber dot says so.
  useEffect(() => saveState.subscribe(({ pending }) => setUnsaved(pending)), []);
  useEffect(() => startSaveQueue(), []);

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
    const fresh = { name: 'New Project', status: 'QUEUED', track: '03', domain: 'AI' };
    // In TODAY, a new card without a block is invisible: block it at the
    // next half hour so the card you just made is the card you can act on.
    if (isToday) Object.assign(fresh, { todayTime: nextHalfHour(), todayDate: localDate() });
    api.post('/projects', fresh)
      .then(({ id }) => {
        api.get('/projects').then(data => { setProjects(data); setOpenId(id); }).catch(() => {});
      })
      .catch(onSaveError);
  };
  // Saves are field-level and debounced: typing in one field sends that
  // field, not the whole card, and rapid keystrokes become one request.
  const enqueueSave = (id, patch, { keepalive = false } = {}) => {
    const previous = saveChains.current.get(id) || Promise.resolve();
    const next = previous.then(() => {
      const body = { ...patch };
      const stamp = saveStamps.current.get(id);
      if (stamp) body.updatedAt = stamp;
      return keepalive
        ? api.putKeepalive(`/projects/${id}`, body)
        : api.put(`/projects/${id}`, body);
    }).then((res) => {
      if (res && res.updatedAt) {
        saveStamps.current.set(id, res.updatedAt);
        setProjects(prev => prev.map(x => x.id === id ? { ...x, updatedAt: res.updatedAt } : x));
      }
    }).catch(onSaveError);
    saveChains.current.set(id, next);
  };
  const scheduleSave = (id, patch) => {
    const entry = pendingSaves.current.get(id) || { patch: {}, timer: null };
    Object.assign(entry.patch, patch);
    clearTimeout(entry.timer);
    entry.timer = setTimeout(() => {
      pendingSaves.current.delete(id);
      enqueueSave(id, entry.patch);
    }, 400);
    pendingSaves.current.set(id, entry);
  };

  useEffect(() => {
    const flush = () => flushPendingSaves(pendingSaves.current, enqueueSave);
    const onVisibility = () => { if (document.visibilityState === "hidden") flush(); };
    window.addEventListener("pagehide", flush);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("pagehide", flush);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

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
    const current = projects.find(x => x.id === p.id);
    const patch = changedFields(current, p);
    if (!Object.keys(patch).length) return;  // nothing actually changed
    setProjects(prev => prev.map(x => x.id === p.id ? { ...p, updatedAt: x.updatedAt } : x));
    scheduleSave(p.id, patch);
  };
  const loadArchived = () => api.get('/projects?archived=1').then(setArchivedProjects).catch(() => {});
  useEffect(() => { if (filter === "ARCHIVED") loadArchived(); }, [filter]);
  useEffect(() => () => clearTimeout(undoTimer.current), []);

  const refreshBoard = () => Promise.all([
    api.get('/projects').then(setProjects),
    api.get('/projects?archived=1').then(setArchivedProjects),
  ]).catch(onSaveError);

  // Archive, not delete: the card, its notes and its log stay on disk.
  const remove = (id) => {
    if (holdEdit(() => remove(id))) return;
    const name = (projects.find(p => p.id === id) || archivedProjects.find(p => p.id === id) || {}).name;
    setProjects(prev => prev.filter(x => x.id !== id));
    if (openId === id) setOpenId(null);
    setUndo({ id, name: name || "Project" });
    clearTimeout(undoTimer.current);
    undoTimer.current = setTimeout(() => setUndo(null), 5000);
    api.del(`/projects/${id}`).then(loadArchived).catch(onSaveError);
  };
  const undoArchive = () => {
    if (!undo) return;
    clearTimeout(undoTimer.current);
    api.put(`/projects/${undo.id}/restore`, {})
      .then(() => { setUndo(null); return refreshBoard(); })
      .catch(onSaveError);
  };
  const restore = (id) => api.put(`/projects/${id}/restore`, {}).then(refreshBoard).catch(onSaveError);

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
  const moveProject = (direction, list, visibleIds) => {
    if (!openId) return;
    if (!list && holdEdit((fresh) => moveProject(direction, fresh, visibleIds))) return;
    const items = list || projects;
    // Move within the list the owner is looking at, not the whole board.
    const visible = visibleIds || items.map(p => p.id);
    const idx = visible.indexOf(openId);
    if (idx === -1) return;
    const swapIdx = direction === "up" ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= visible.length) return;
    const newVisible = [...visible];
    [newVisible[idx], newVisible[swapIdx]] = [newVisible[swapIdx], newVisible[idx]];
    // Optimistic: fill the visible rows' own slots with the new order.
    const visibleSet = new Set(visible);
    const slots = [];
    items.forEach((p, i) => { if (visibleSet.has(p.id)) slots.push(i); });
    const byId = new Map(items.map(p => [p.id, p]));
    const newProjects = [...items];
    slots.forEach((slot, k) => { newProjects[slot] = byId.get(newVisible[k]); });
    setProjects(newProjects);
    api.put('/projects/order', { ids: newVisible })
      .then(() => api.get('/projects').then(setProjects))
      .catch(onSaveError);
  };

  const isToday = filter === "TODAY";
  const flapSize = parseInt(settings.fontSize) || 104;
  const flapAlign = settings.alignment || "left";

  // Standard filters
  const today = localDate();
  const filtered = visibleProjects(projects, archivedProjects, filter, today);
  const counts = filterCounts(projects, archivedProjects, today);
  const visibleIds = filtered.map(p => p.id);

  // TODAY view: build unified timeline
  const todayTimeline = (() => {
    if (!isToday) return [];
    const items = [];

    filtered.forEach((p) => {
      items.push({ type: "project", time: p.todayTime, data: p, sortKey: timeToMinutes(p.todayTime) });
    });

    events.filter((ev) => !ev.date || ev.date === today).forEach((ev) => {
      items.push({ type: "event", time: ev.time, data: ev, sortKey: timeToMinutes(ev.time) });
    });

    // Demo-only: the mock inbox belongs to the seed board, not a real one.
    if (settings.demo) MOCK_EMAILS.forEach((em) => {
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
    ? projects.filter((p) => p.status !== "SHIPPED" && p.status !== "QUEUED"
        && (!p.todayTime || p.todayDate !== today))
    : [];

  // Clock + session pulse
  const [now, setNow] = useState(new Date());
  useEffect(() => { const t = window.setInterval(() => setNow(new Date()), 1000); return () => window.clearInterval(t); }, []);
  const time = now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
  const date = now.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }).toUpperCase();

  // NEXT UP — the one card the board points at. Its next action is also
  // the plain-words START HERE line under the header.
  const nextUp = nextUpProject(projects);
  const nextUpId = nextUp ? nextUp.id : null;
  const startHere = startHereText(nextUp, nextUp && !visibleIds.includes(nextUp.id)
    ? (isToday ? "in No time blocked" : `in ${nextUp.status}`)
    : null);

  const intervals = [0.06, 0.12, 0.25, 0.5, 1.0];
  const filters = FILTERS;

  if (!ready) return (
    <div style={{ background: BG, color: G4, height: "100vh", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: DISPLAY, fontSize: "14px", letterSpacing: "0.2em", textRendering: "optimizeLegibility" }}>LOADING</div>
  );

  const cardProps = (p) => ({
    project: p, onUpdate: update, onDelete: remove, onRestore: restore,
    open: openId === p.id,
    onToggle: () => setOpenId(openId === p.id ? null : p.id),
    isNextUp: p.id === nextUpId,
    flapSize: flapSizeFor({ width: vw, text: p.name, preferred: flapSize }),
    flapAlign, readOnly: isViewer,
  });

  return (
    <div className="board" style={{ background: BG, minHeight: "100vh", fontFamily: MONO }}>

      {/* HEADER */}
      <div style={{ padding: "24px 24px 12px", borderBottom: `1px solid ${G4}` }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          {/* Left: title + date + pulse */}
          <div>
            <h1 style={{ fontFamily: DISPLAY, fontSize: "16px", fontWeight: 400, color: WHITE, letterSpacing: "0.1em", margin: 0, lineHeight: 1, textTransform: "uppercase", textRendering: "optimizeLegibility" }}>
              {isToday ? "Today" : "Departures"}
            </h1>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "4px" }}>
              <div style={whisper({ letterSpacing: "0.12em" })}>
                {isToday ? date : "USD-COMPOSED PROJECT STATE"}
              </div>
              <div title={formatDuration(sessionMins)} style={{ width: "5px", height: "5px", borderRadius: "50%", background: sessionColor(sessionMins), transition: "background 0.3s ease", cursor: "default" }} />
              {unsaved > 0 && (
                <div role="status"
                  title={`${unsaved} change${unsaved === 1 ? "" : "s"} not saved yet. The board is retrying; keep this tab open until the dot clears.`}
                  style={{ width: "5px", height: "5px", borderRadius: "50%", background: ACCENT, cursor: "default" }} />
              )}
            </div>
            {reloadNotice && (
              <div
                role="status"
                title="The board was changed on the server since this page loaded (for example by a restore), so this page reloaded the projects to match. Edits held during the reload were re-applied to the board as it is now."
                style={whisper({ letterSpacing: "0.12em", marginTop: "4px", whiteSpace: "nowrap", cursor: "default" })}
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
                style={whisper({ color: RISK, letterSpacing: "0.12em", marginTop: "4px", whiteSpace: "nowrap", cursor: "default" })}
              >
                {backup.problem === "damaged" ? "BOARD MAY BE DAMAGED" : "BACKUP FAILED"}
              </div>
            )}
            {clockWrong && (
              <div
                role="status"
                title="The PC clock is behind the newest backup, so backups are kept separately and nothing is pruned until the clock is right. Set the clock forward to let old backups be cleaned up again."
                style={whisper({ color: RISK, letterSpacing: "0.12em", marginTop: "4px", whiteSpace: "nowrap", cursor: "default" })}
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
                  <div style={whisper({ fontWeight: 600, textAlign: "right" })}>{weather.temp}° {weather.desc.toUpperCase()}</div>
                  <div style={whisper({ marginTop: "2px", textAlign: "right" })}>{weather.city}</div>
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
            </div>
          </div>
        </div>
      </div>

      {/* START HERE — the one line the board says out loud in amber */}
      <div style={{ display: "flex", alignItems: "baseline", gap: "12px", padding: "12px 24px", borderBottom: `1px solid ${G4}` }}>
        <span style={sys("11px", ACCENT, { fontWeight: 700, letterSpacing: "0.14em", flexShrink: 0 })}>START HERE</span>
        <span style={{ width: "24px", height: "2px", background: ACCENT, alignSelf: "center", flexShrink: 0 }} />
        <span style={sentence({ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{startHere}</span>
      </div>

      {/* FILTERS */}
      <div className="filters-bar" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 24px", borderBottom: `1px solid ${G4}` }}>
        <div className="filter-row" style={{ display: "flex" }}>
          {filters.map((f) => (
            <button key={f} onClick={() => setFilter(f)} style={{
              background: "transparent", border: "none", fontFamily: MONO, fontSize: "11px",
              fontWeight: filter === f ? 700 : 400, color: filter === f ? WHITE : WHISPER,
              letterSpacing: "0.1em", padding: "8px 10px", cursor: "pointer", transition: "color 0.12s",
            }}>
              {f}
              <span style={{ marginLeft: "5px", color: filter === f ? WHITE : WHISPER, fontVariantNumeric: "tabular-nums" }}>
                {counts[f] ?? 0}
              </span>
            </button>
          ))}
        </div>
        {/* DISPLAY — speed, size and alignment in one place */}
        <div style={{ position: "relative" }}>
          <button onClick={() => setShowDisplay(v => !v)} aria-expanded={showDisplay}
            style={{ background: "transparent", border: `1px solid ${G4}`, color: WHITE,
                     fontFamily: MONO, fontSize: "11px", letterSpacing: "0.1em", padding: "7px 10px",
                     borderRadius: "4px", cursor: "pointer" }}>DISPLAY</button>
          {showDisplay && (
            <>
              <div onClick={() => setShowDisplay(false)}
                style={{ position: "fixed", inset: 0, zIndex: 39 }} />
              <div role="menu" className="display-menu" style={{ position: "absolute", right: 0, top: "calc(100% + 8px)", zIndex: 40,
                    width: "224px", background: G6, border: `1px solid ${G4}`, borderRadius: "4px",
                    padding: "12px", display: "flex", flexDirection: "column", gap: "12px" }}>
                <div>
                  <div style={whisper({ letterSpacing: "0.12em" })}>SPEED</div>
                  <div style={{ display: "flex", gap: "2px", marginTop: "6px" }}>
                    {intervals.map(v => (
                      <button key={v} onClick={() => setInterval_(v)} style={{
                        flex: 1, background: interval === v ? G4 : "transparent",
                        border: `1px solid ${interval === v ? WHITE : G4}`, color: interval === v ? WHITE : WHISPER,
                        fontFamily: MONO, fontSize: "10px", padding: "6px 0", borderRadius: "4px", cursor: "pointer",
                      }}>{v < 1 ? `.${String(v).split(".")[1]}` : "1s"}</button>
                    ))}
                  </div>
                </div>
                <div>
                  <div style={whisper({ letterSpacing: "0.12em" })}>SIZE</div>
                  <div style={{ display: "flex", gap: "2px", marginTop: "6px" }}>
                    {FONT_SIZES.map(fs => (
                      <button key={fs.label} onClick={() => saveSetting("fontSize", String(fs.value))} style={{
                        flex: 1, background: parseInt(settings.fontSize) === fs.value ? G4 : "transparent",
                        border: `1px solid ${parseInt(settings.fontSize) === fs.value ? WHITE : G4}`,
                        color: parseInt(settings.fontSize) === fs.value ? WHITE : WHISPER,
                        fontFamily: MONO, fontSize: "10px", padding: "6px 0", borderRadius: "4px", cursor: "pointer",
                      }}>{fs.label}</button>
                    ))}
                  </div>
                </div>
                <div>
                  <div style={whisper({ letterSpacing: "0.12em" })}>ALIGN</div>
                  <div style={{ display: "flex", gap: "2px", marginTop: "6px" }}>
                    {["left", "center", "right"].map(a => (
                      <button key={a} onClick={() => saveSetting("alignment", a)} style={{
                        flex: 1, background: settings.alignment === a ? G4 : "transparent",
                        border: `1px solid ${settings.alignment === a ? WHITE : G4}`,
                        color: settings.alignment === a ? WHITE : WHISPER,
                        fontFamily: MONO, fontSize: "10px", padding: "6px 0", borderRadius: "4px", cursor: "pointer",
                      }}>{a === "left" ? "LEFT" : a === "center" ? "CENTER" : "RIGHT"}</button>
                    ))}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* VIEWER BANNER */}
      {isViewer && (
        <div style={{ padding: "8px 24px", background: G6, borderBottom: `1px solid ${G4}`, textAlign: "center" }}>
          <span style={whisper({ letterSpacing: "0.08em" })}>VIEWING · READ ONLY</span>
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
                  <EventRow event={item.data} projects={projects} open={openEventId === item.data.id}
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
            {filter === "ALL"
              ? groupByTrack(filtered).map((group) => (
                  <div key={group.track} style={{ display: "contents" }}>
                    <SectionLabel label={`TRACK ${group.track} · ${group.count}`} />
                    {group.items.map((p, i) => (
                      <div key={`${p.id}-${animKey}`} className="arrive" style={{ animationDelay: `${i * interval}s`, padding: "0 12px" }}>
                        <ProjectCard {...cardProps(p)} showTime={false} />
                      </div>
                    ))}
                  </div>
                ))
              : filtered.map((p, i) => (
                  <div key={`${p.id}-${animKey}`} className="arrive" style={{ animationDelay: `${i * interval}s`, padding: "0 12px" }}>
                    <ProjectCard {...cardProps(p)} showTime={false} />
                  </div>
                ))}
          </>
        )}

        {!isToday && filtered.length === 0 && (
          <div style={{ padding: "48px 36px", textAlign: "center" }}>
            <div style={{ fontFamily: DISPLAY, fontSize: "14px", color: WHISPER, letterSpacing: "0.2em", textRendering: "optimizeLegibility" }}>{filter === "ALL" ? "NO ACTIVE DEPARTURES" : `NO ${filter} PROJECTS`}</div>
          </div>
        )}
      </div>

      {/* ACTIONS */}
      <div className="actions" style={{ position: "fixed", bottom: "24px", right: "24px", display: "flex", gap: "8px", zIndex: 50 }}>
        {!isViewer && isToday && (
          <button onClick={addEvent} title="Add event" style={{
            width: "36px", height: "36px", borderRadius: "50%",
            background: G5, border: `1px solid ${G4}`,
            color: WHISPER, fontFamily: MONO, fontSize: "11px", fontWeight: 700,
            cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
            transition: "all 0.15s", letterSpacing: "0.02em",
          }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = WHISPER; e.currentTarget.style.color = WHITE; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = G4; e.currentTarget.style.color = WHISPER; }}>
            {isPhone ? "EVENT" : "EV+"}
          </button>
        )}
        {!isViewer && (
          <button onClick={() => { loadViewers(); setShowShare(true); }} title="Share board" style={{
            width: "44px", height: "44px", borderRadius: "50%",
            background: G5, border: `1px solid ${G4}`,
            color: WHISPER, fontFamily: MONO, fontSize: "11px", fontWeight: 700,
            cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
            transition: "all 0.15s", letterSpacing: "0.02em",
          }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = WHISPER; e.currentTarget.style.color = WHITE; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = G4; e.currentTarget.style.color = WHISPER; }}>
            {isPhone ? "SHARE" : "SHR"}
          </button>
        )}
        <button onClick={() => setShowRecap(true)} style={{
          width: "44px", height: "44px", borderRadius: "50%",
          background: G5, border: `1px solid ${G4}`,
          color: WHISPER, fontFamily: MONO, fontSize: "11px", fontWeight: 700,
          cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
          transition: "all 0.15s", letterSpacing: "0.02em",
        }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = WHISPER; e.currentTarget.style.color = WHITE; }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = G4; e.currentTarget.style.color = WHISPER; }}>
          {isPhone ? "RECAP" : "REC"}
        </button>
        {!isViewer && !isPhone && (
          <button onClick={() => moveProject("up", undefined, visibleIds)} title="Move up" style={{
            width: "44px", height: "44px", borderRadius: "50%",
            background: G5, border: openId ? `1px solid ${G4}` : "none",
            color: openId ? WHITE : G3, fontFamily: MONO, fontSize: "14px", fontWeight: 400,
            cursor: openId ? "pointer" : "default", display: "flex", alignItems: "center", justifyContent: "center",
            transition: "all 0.15s", lineHeight: 1,
          }}
            onMouseEnter={(e) => { if (openId) { e.currentTarget.style.borderColor = WHITE; } }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = openId ? G4 : "transparent"; }}>{isPhone ? "UP" : "▲"}</button>
        )}
        {!isViewer && !isPhone && (
          <button onClick={() => moveProject("down", undefined, visibleIds)} title="Move down" style={{
            width: "44px", height: "44px", borderRadius: "50%",
            background: G5, border: openId ? `1px solid ${G4}` : "none",
            color: openId ? WHITE : G3, fontFamily: MONO, fontSize: "14px", fontWeight: 400,
            cursor: openId ? "pointer" : "default", display: "flex", alignItems: "center", justifyContent: "center",
            transition: "all 0.15s", lineHeight: 1,
          }}
            onMouseEnter={(e) => { if (openId) { e.currentTarget.style.borderColor = WHITE; } }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = openId ? G4 : "transparent"; }}>{isPhone ? "DOWN" : "▼"}</button>
        )}
        {!isViewer && !isPhone && (
          <button onClick={() => openId && remove(openId)} style={{
            width: "44px", height: "44px", borderRadius: "50%",
            background: openId ? G4 : G5, border: "none",
            color: openId ? WHITE : G3, fontFamily: DISPLAY, fontSize: "22px", fontWeight: 300,
            cursor: openId ? "pointer" : "default", display: "flex", alignItems: "center", justifyContent: "center",
            transition: "all 0.15s", lineHeight: 1, paddingBottom: "2px",
          }}
            onMouseEnter={(e) => { if (openId) { e.currentTarget.style.background = RED; e.currentTarget.style.color = "#000"; } }}
            onMouseLeave={(e) => { e.currentTarget.style.background = openId ? G4 : G5; e.currentTarget.style.color = openId ? WHITE : G3; }}>{isPhone ? "ARCHIVE" : "−"}</button>
        )}
        {!isViewer && (
          <button onClick={add} style={{
            width: "44px", height: "44px", borderRadius: "50%",
            background: WHITE, border: "none", color: BG,
            fontFamily: DISPLAY, fontSize: "22px", fontWeight: 500, cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
            transition: "all 0.15s", lineHeight: 1, paddingBottom: "2px",
          }}
            onMouseEnter={(e) => e.currentTarget.style.transform = "scale(1.06)"}
            onMouseLeave={(e) => e.currentTarget.style.transform = "scale(1)"}>{isPhone ? "NEW" : "+"}</button>
        )}
      </div>

      {/* RECAP MODAL */}
      {showRecap && <RecapPanel projects={projects} sessionMins={sessionMins} onClose={() => setShowRecap(false)} />}

      {/* SHARE MODAL */}
      {showShare && <SharePanel viewers={viewers} onAdd={addViewer} onRemove={removeViewer}
        onClose={() => setShowShare(false)} newEmail={newViewerEmail} setNewEmail={setNewViewerEmail} />}

      {/* FOOTER */}
      <div style={{ padding: "24px 24px 48px", textAlign: "center" }}>
        <span style={whisper({ letterSpacing: "0.2em" })}>DEPARTURES {version} · USD-COMPOSED · SOLARI PROTOCOL</span>
      </div>

      {undo && (
        <div role="status" style={{
          position: "fixed", left: "24px", bottom: "24px", zIndex: 60,
          display: "flex", alignItems: "center", gap: "14px",
          background: G5, border: `1px solid ${G4}`, borderRadius: "4px",
          padding: "10px 14px", boxShadow: "0 8px 24px #00000088",
        }}>
          <span style={sys("11px", WHISPER, { letterSpacing: "0.1em" })}>ARCHIVED · {(undo.name || "").toUpperCase()}</span>
          <button onClick={undoArchive} style={{
            ...sys("11px", WHITE), background: "transparent", border: `1px solid ${G4}`,
            padding: "6px 10px", borderRadius: "4px", cursor: "pointer", letterSpacing: "0.1em",
          }}>UNDO</button>
        </div>
      )}
    </div>
  );
}
