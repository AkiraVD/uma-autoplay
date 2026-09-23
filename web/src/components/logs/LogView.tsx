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

function StatBars({ stats, headroom }: { stats: string; headroom?: string }) {
  const values = parseDict(stats);
  const room = parseDict(headroom);
  if (!values) {
    return <div className="font-mono text-sm break-words">{stats}</div>;
  }
  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-x-4 gap-y-3">
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
            <div className="flex items-baseline justify-between gap-1">
              <span className="text-xs text-muted-foreground">{label}</span>
              {capped && (
                <span className="text-[10px] font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">capped</span>
              )}
            </div>
            <div className="text-xl font-semibold tabular-nums">{value}</div>
            <div className="mt-1 h-1.5 rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full rounded-full ${capped ? "bg-amber-500" : colour}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="mt-0.5 text-[11px] text-muted-foreground">
              {left == null ? " " : capped ? "at cap" : `${left} to cap`}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Field({ label, value, big }: { label: string; value?: string | null; big?: boolean }) {
  if (value == null) return null;
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className={`font-semibold break-words ${big ? "text-xl" : "text-lg"}`}>{value}</div>
    </div>
  );
}

const CARD = "bg-card p-5 rounded-xl shadow-lg border border-border/20";

export default function LogView() {
  const [data, setData] = useState<LogData | null>(null);
  // Every failure carries a code: plain words get read as a diagnosis.
  const [fault, setFault] = useState<string | null>(null);
  const [follow, setFollow] = useState(true);
  const tailRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const res = await fetch(`${URL}/logs/data`, { cache: "no-store" });
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
  }, []);

  useEffect(() => {
    if (follow && tailRef.current) tailRef.current.scrollTop = tailRef.current.scrollHeight;
  }, [data, follow]);

  const status = data?.status;
  const since = status?.secs_since_log;
  const dot = !status || status.state !== "running" ? "bg-red-600"
    : since != null && since > 120 ? "bg-amber-500" : "bg-green-600";
  const energy = data?.energy != null ? `${Math.round(parseFloat(data.energy))}%` : null;
  // Careers this run has *started by itself*, which is exactly what the limit
  // counts - so the two always agree and "3/3" is the run about to stop. Not
  // "which career we are on": a career already in progress when the bot started
  // is not one of these, and numbering from it would put every later reading
  // one out. Hidden when career_start is off, where the count is always 0.
  const careers = data?.careers;
  const careerLabel = careers?.enabled
    ? `careers started ${careers.started}${careers.limit ? `/${careers.limit}` : ""}`
    : null;

  return (
    <div className="flex flex-col gap-6">
      <div className={CARD}>
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <h2 className="text-3xl font-semibold flex items-center gap-3">
            <ScrollText className="text-primary" />
            Live Log
          </h2>
          <div className="flex items-center gap-2 text-muted-foreground">
            <span className={`inline-block w-2.5 h-2.5 rounded-full ${dot}`} />
            <span>{status ? `Bot ${status.state}` : "LOG-E04 no status yet"}</span>
            {careerLabel && <span>· {careerLabel}</span>}
            {since != null && <span>· log {since}s ago</span>}
          </div>
        </div>
        {fault && (
          <div className="mb-4 rounded-lg border border-red-600/40 bg-red-600/10 p-3 font-mono text-sm">{fault}</div>
        )}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Field label="Year" value={data?.year} big />
          <Field label="Turn" value={data?.turn} />
          <Field label="Mood" value={data?.mood} />
          <Field label="Energy" value={energy} />
        </div>
        <div className="mt-4 flex flex-col gap-4">
          <Field label="Goal" value={data?.criteria} />
          <Field label="Last action" value={data?.action} />
          {data?.reason && (
            <div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground">Why</div>
              <div className="font-mono text-sm break-words">{data.reason}</div>
            </div>
          )}
          {data?.stats && (
            <div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground mb-2">Stats</div>
              <StatBars stats={data.stats} headroom={data.headroom} />
            </div>
          )}
        </div>
      </div>

      {data?.trouble && data.trouble.length > 0 && (
        <div className={`${CARD} border-amber-500/60 bg-amber-500/5`}>
          <div className="text-xs uppercase tracking-wide text-amber-600 dark:text-amber-400 mb-2">Recent trouble</div>
          <div className="font-mono text-xs leading-relaxed break-words">
            {data.trouble.map((line, i) => <LogLine key={i} line={line} />)}
          </div>
        </div>
      )}

      <div className={CARD}>
        <div className="flex items-center justify-between mb-2">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">Log</div>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} />
            Follow
          </label>
        </div>
        <div ref={tailRef} className="font-mono text-xs leading-relaxed break-words max-h-[60vh] overflow-y-auto">
          {(data?.recent ?? []).map((line, i) => <LogLine key={i} line={line} />)}
        </div>
      </div>
    </div>
  );
}
