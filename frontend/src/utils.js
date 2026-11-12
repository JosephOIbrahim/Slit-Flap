import { ACCENT, RED, G3, G4 } from "./theme";

export { localDate, nextHalfHour } from "./time";

// ─── DEPARTURE STATUS (deadline → board language) ────────────

const MS_DAY = 86400000;
const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();

// Deadline rendered as departure-board language. null = nothing to say.
export function departure(p) {
  if (!p.deadline || p.status === "SHIPPED") return null;
  const dl = new Date(p.deadline + "T00:00:00");
  if (isNaN(dl.getTime())) return null;
  const days = Math.round((startOfDay(dl) - startOfDay(new Date())) / MS_DAY);
  if (days < 0) return { label: `DELAYED ${-days}D`, color: RED, days };
  if (days === 0) return { label: "DEPARTS TODAY", color: ACCENT, days };
  if (days <= 7) return { label: `DEPARTS ${days}D`, color: ACCENT, days };
  return null;
}

// ─── NEXT UP SCORING ─────────────────────────────────────────

export function scoreProject(p) {
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
  const dep = departure(p);
  if (dep) score += dep.days < 0 ? 35 : Math.max(0, 24 - dep.days * 3);
  return score;
}

// ─── RELATIVE TIME ───────────────────────────────────────────

export function relTime(iso) {
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

export function sessionColor(mins) {
  if (mins < 120) return "#3a5a3a";
  if (mins < 240) return "#5a4a2a";
  return "#4a2a2a";
}

export function formatDuration(mins) {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export function statusColor(s) {
  if (s === "ACTIVE" || s === "ROLLING") return ACCENT;
  if (s === "BLOCKED") return RED;
  if (s === "SHIPPED") return G3;
  return G4;
}

export function timeToMinutes(t) {
  if (!t) return 9999;
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
}

// ─── WEATHER ─────────────────────────────────────────────────

const WMO_DESC = {0:"Clear",1:"Mostly Clear",2:"Partly Cloudy",3:"Overcast",45:"Fog",48:"Rime Fog",51:"Lt Drizzle",53:"Drizzle",55:"Hvy Drizzle",61:"Lt Rain",63:"Rain",65:"Hvy Rain",71:"Lt Snow",73:"Snow",75:"Hvy Snow",80:"Showers",95:"Thunderstorm"};

export async function fetchWeather(zip) {
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
