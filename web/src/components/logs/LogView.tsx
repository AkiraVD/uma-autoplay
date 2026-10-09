import { useEffect, useRef, useState } from "react";
import { ScrollText } from "lucide-react";
import { URL } from "@/constants";

// What /logs/data returns: tools/logserver.py's snapshot of logs/log.txt,
// scoped to the career in progress, plus the bot's state from the server.
type LogData = {
  year?: string;
  turn?: string;
  mood?: string;
  energy?: string;
  criteria?: string;
  action?: string;
  reason?: string;
  stats?: string;
  headroom?: string;
  trouble?: string[];
  recent?: string[];
  status?: { state: string; secs_since_log: number | null } | null;
  // Which career of this run the bot is on. Absent from an older server.
  careers?: { started: number; limit: number; enabled: boolean } | null;
};

const POLL_MS = 3000;
// Kept per browser, not in the config: which detail someone wants to read is a
// property of the device they are reading on, and it must not ride along in a
// preset. Wrapped because storage throws in a private window.
const DEBUG_KEY = "uma-log-debug";
function storedDebug() {
  try {
    return localStorage.getItem(DEBUG_KEY) !== "0";
  } catch {
    return true;
  }
}
const LEVEL = /^(\d{2}:\d{2}:\d{2}) (DEBUG|INFO|WARNING|ERROR)(\s+)(.*)$/;
const LEVEL_CLASS: Record<string, string> = {
  DEBUG: "text-muted-foreground",
  INFO: "text-sky-600 dark:text-sky-400",
  WARNING: "text-amber-600 dark:text-amber-400",
  ERROR: "text-red-600 dark:text-red-400",
};

function LogLine({ line }: { line: string }) {
  const m = LEVEL.exec(line);
  if (!m) return <div>{line}</div>;
  return (
    <div>
      <span className="text-muted-foreground">{m[1]}</span>{" "}
      <span className={`font-bold ${LEVEL_CLASS[m[2]]}`}>{m[2]}</span>
      {m[3]}
      {m[4]}
    </div>
  );
}

// The bot logs both dicts as Python reprs ({'spd': 1100, ...}), which is JSON
// once the quotes are swapped. A read that does not parse is shown raw rather
// than dropped, so a change in the log format is visible instead of silent.
function parseDict(raw?: string): Record<string, number> | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw.replace(/'/g, '"'));
    if (!parsed || typeof parsed !== "object") return null;
    return parsed as Record<string, number>;
  } catch {
    return null;
  }
}

const STATS: [key: string, label: string, colour: string][] = [
  ["spd", "Speed", "bg-sky-500"],
  ["sta", "Stamina", "bg-red-500"],
  ["pwr", "Power", "bg-amber-500"],
  ["guts", "Guts", "bg-pink-500"],
  ["wit", "Wit", "bg-emerald-500"],
];

// One row per stat rather than the old five-across grid: in a 300px rail the
// label sits beside the number instead of above it, which is what makes five
// of them fit in the height of the log beside them.
function StatBars({ stats, headroom }: { stats: string; headroom?: string }) {
  const values = parseDict(stats);
  const room = parseDict(headroom);
  if (!values) {
    return <div className="font-mono text-sm break-words">{stats}</div>;
  }
  return (
    <div className="flex flex-col gap-3.5">
      {STATS.map(([key, label, colour]) => {
        const value = values[key];
        if (value == null) return null;
        const left = room?.[key];
        const capped = left === 0;
        // Without headroom there is no cap to scale against, so the bar fills.
        const cap = left != null ? value + left : null;
        const pct = cap && cap > 0 ? Math.min(100, (value / cap) * 100) : 100;
        return (
          <div key={key}>
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-[13px] text-muted-foreground">{label}</span>
              <div className="flex items-baseline gap-2">
                {capped && (
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">capped</span>
                )}
                <span className="text-lg font-semibold tabular-nums">{value}</span>
              </div>
            </div>
            <div className="mt-1 h-1.5 rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full rounded-full ${capped ? "bg-amber-500" : colour}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="mt-0.5 text-[11px] text-muted-foreground">
              {left == null ? " " : capped ? "at cap" : `${left} to cap`}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Field({ label, value }: { label: string; value?: string | null }) {
  if (value == null) return null;
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="font-semibold break-words text-[15px]">{value}</div>
    </div>
  );
}

// One of the four readings in the strip across the top. Those are what gets
// glanced at, so they stay full width and on one line rather than going into
// the rail with everything else.
function Reading({ label, value, warn }: { label: string; value?: string | null; warn?: boolean }) {
  if (value == null) return null;
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className={`text-[17px] font-semibold ${warn ? "text-amber-600 dark:text-amber-400" : ""}`}>{value}</div>
    </div>
  );
}

const CARD = "bg-card rounded-xl shadow-lg border border-border/20";

export default function LogView() {
  const [data, setData] = useState<LogData | null>(null);
  // Every failure carries a code: plain words get read as a diagnosis.
  const [fault, setFault] = useState<string | null>(null);
  const [follow, setFollow] = useState(true);
  const [debug, setDebug] = useState(storedDebug);
  const tailRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        // Filtered on the server, so hiding DEBUG still returns a full window
        // of the lines that are left rather than the few that survived a slice.
        const res = await fetch(`${URL}/logs/data?debug=${debug ? "1" : "0"}`,
                                { cache: "no-store" });
        if (!res.ok) throw new Error(`LOG-E02 the server answered HTTP ${res.status}`);
        let json: LogData;
        try {
          json = await res.json();
        } catch {
          throw new Error("LOG-E03 the server answered with something that is not JSON");
        }
        if (alive) {
          setData(json);
          setFault(null);
        }
      } catch (e) {
        const msg = e instanceof Error && e.message.startsWith("LOG-") ? e.message
          : "LOG-E01 could not reach /logs/data - is main.py running?";
        if (alive) setFault(msg);
      }
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
    // Re-runs on a toggle so the change shows on the next frame, not the next poll.
  }, [debug]);

  useEffect(() => {
    if (follow && tailRef.current) tailRef.current.scrollTop = tailRef.current.scrollHeight;
  }, [data, follow]);

  const status = data?.status;
  const since = status?.secs_since_log;
  const dot = !status || status.state !== "running" ? "bg-red-600"
    : since != null && since > 120 ? "bg-amber-500" : "bg-green-600";
  const energyValue = data?.energy != null ? Math.round(parseFloat(data.energy)) : null;
  const energy = energyValue != null ? `${energyValue}%` : null;
  // Careers this run has *started by itself*, which is exactly what the limit
  // counts - so the two always agree and "3/3" is the run about to stop. Not
  // "which career we are on": a career already in progress when the bot started
  // is not one of these, and numbering from it would put every later reading
  // one out. Hidden when career_start is off, where the count is always 0.
  const careers = data?.careers;
  const careerLabel = careers?.enabled
    ? `careers started ${careers.started}${careers.limit ? `/${careers.limit}` : ""}`
    : null;
  const trouble = data?.trouble ?? [];

  return (
    <div className="flex flex-col gap-5">
      {/* The strip. Year / Turn / Mood / Energy are the glance, so they keep the
          full width and read left to right instead of going into the rail. */}
      <div className={`${CARD} px-5 py-3.5 flex flex-wrap items-center gap-x-7 gap-y-3`}>
        <h2 className="text-[22px] font-semibold flex items-center gap-2.5">
          <ScrollText className="text-primary" size={22} />
          Live Log
        </h2>
        <div className="flex items-center gap-2">
          <span className={`inline-block w-2.5 h-2.5 rounded-full ${dot}`} />
          <span className="text-sm font-semibold">{status ? `Bot ${status.state}` : "LOG-E04 no status"}</span>
        </div>
        <div className="hidden sm:block self-stretch w-px bg-border" />
        <Reading label="Year" value={data?.year} />
        <Reading label="Turn" value={data?.turn} />
        <Reading label="Mood" value={data?.mood} />
        <Reading label="Energy" value={energy} warn={energyValue != null && energyValue < 35} />
        <div className="sm:ml-auto text-[13px] text-muted-foreground">
          {careerLabel}
          {careerLabel && since != null && " · "}
          {since != null && `log ${since}s ago`}
        </div>
      </div>

      {fault && (
        <div className="rounded-lg border border-red-600/40 bg-red-600/10 p-3 font-mono text-sm">{fault}</div>
      )}

      {/* The rail comes first in the markup, so when the two wrap it lands on
          top of the log with no reordering. Above lg the order swap puts the
          log back on the left and the rail alongside it on the right. */}
      <div className="flex flex-wrap gap-5 items-start">
        <aside className="basis-full flex flex-wrap gap-4 items-start lg:order-2 lg:basis-[300px] lg:max-w-[320px] lg:grow-0 lg:flex-col lg:flex-nowrap">
          {data?.stats && (
            <div className={`${CARD} p-4 grow basis-[320px] lg:basis-auto lg:w-full lg:grow-0`}>
              <div className="text-xs uppercase tracking-wide text-muted-foreground mb-3">Stats</div>
              <StatBars stats={data.stats} headroom={data.headroom} />
            </div>
          )}
          <div className={`${CARD} p-4 grow basis-[320px] lg:basis-auto lg:w-full lg:grow-0 flex flex-col gap-3`}>
            <Field label="Goal" value={data?.criteria} />
            <Field label="Last action" value={data?.action} />
            {data?.reason && (
              <div>
                <div className="text-xs uppercase tracking-wide text-muted-foreground">Why</div>
                <div className="font-mono text-xs leading-relaxed break-words">{data.reason}</div>
              </div>
            )}
          </div>
          {trouble.length > 0 && (
            <div className="basis-full lg:w-full rounded-xl border border-amber-500/60 bg-amber-500/5 p-4">
              <div className="text-xs uppercase tracking-wide text-amber-600 dark:text-amber-400 mb-1.5">Recent trouble</div>
              <div className="font-mono text-[11px] leading-relaxed break-words">
                {trouble.map((line, i) => <LogLine key={i} line={line} />)}
              </div>
            </div>
          )}
        </aside>

        <div className={`${CARD} p-4 basis-full min-w-0 lg:order-1 lg:grow-[999] lg:basis-[560px]`}>
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">Log</div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <input
                  type="checkbox"
                  checked={debug}
                  onChange={(e) => {
                    setDebug(e.target.checked);
                    try {
                      localStorage.setItem(DEBUG_KEY, e.target.checked ? "1" : "0");
                    } catch {
                      // A private window keeps the toggle for this page only.
                    }
                  }}
                />
                Debug
              </label>
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} />
                Follow
              </label>
            </div>
          </div>
          {/* Fixed rather than capped, so the log is a panel the rail sits
              beside instead of a block that grows past it. Short when stacked,
              so the rail above it and the head of the log share one screen. */}
          <div
            ref={tailRef}
            className="font-mono text-xs leading-relaxed break-words border-t border-border/40 pt-2.5 h-[20rem] lg:h-[calc(100vh-15rem)] overflow-y-auto"
          >
            {(data?.recent ?? []).map((line, i) => <LogLine key={i} line={line} />)}
          </div>
        </div>
      </div>
    </div>
  );
}
