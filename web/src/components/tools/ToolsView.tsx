import { useCallback, useEffect, useRef, useState } from "react";
import {
  Camera,
  FastForward,
  HeartPulse,
  Keyboard,
  Loader2,
  MousePointerClick,
  Power,
  PowerOff,
  Radar,
  RefreshCw,
  ScanSearch,
  SkipForward,
  Wrench,
  type LucideIcon,
} from "lucide-react";

import { URL } from "@/constants";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "../ui/dialog";

// What /tools/status returns; see server/tools.py.
type Job = {
  id: string;
  name: string;
  label: string;
  argv: string[];
  state: "running" | "done" | "failed" | "timed out";
  started: number;
  ended: number | null;
  exit_code: number | null;
  lines: string[];
  image: string | null;
};
type Status = { bot_running: boolean; job: Job | null };

type Tool = { name: string; label: string; hint: string; icon: LucideIcon; locked?: boolean; confirm?: string };

const GROUPS: { title: string; note?: string; tools: Tool[] }[] = [
  {
    title: "Check",
    note: "Read-only, safe at any time.",
    tools: [
      { name: "health", label: "Health check", hint: "Bot process, turn progress, display, game window and a screenshot", icon: HeartPulse },
      { name: "shot", label: "Screenshot", hint: "Capture the game screen", icon: Camera },
      { name: "where", label: "Where am I", hint: "Name the current screen from the buttons on it", icon: ScanSearch },
    ],
  },
  {
    title: "Game",
    tools: [
      { name: "launch", label: "Launch game", hint: "Start the game through Steam, or bring its window back", icon: Power },
      {
        name: "close",
        label: "Close game",
        hint: "Close the game window; whatever is on screen is abandoned",
        icon: PowerOff,
        locked: true,
        confirm: "Close the game? Whatever is on screen is abandoned.",
      },
    ],
  },
  {
    title: "Career helpers",
    note: "These click the game, so they only run while the bot is stopped.",
    tools: [
      { name: "advance", label: "Advance to lobby", hint: "From the title or home screen, resume the career, then tap through to the career lobby", icon: FastForward, locked: true },
      { name: "skiprace", label: "Skip race", hint: "Press skip until the race results", icon: SkipForward, locked: true },
      { name: "scan", label: "Facility scan", hint: "Visit every training facility and report the Unity icons", icon: Radar, locked: true },
    ],
  },
];

const CLICK: Tool = { name: "click", label: "Click at X,Y", hint: "Tap one point on the game screen, then capture", icon: MousePointerClick, locked: true };
// The headless display has no keyboard, so a text field on it can only be
// filled from here. Focusing the field is Click at X,Y's job; this only sends
// the keys, so printable ASCII is all the game's keyboard can take.
const TYPE: Tool = { name: "type", label: "Type text", hint: "Type into the field you already tapped", icon: Keyboard, locked: true };
const MAX_TYPE = 120;

const POLL_MS = 1500;
const CARD = "bg-card p-5 rounded-xl shadow-lg border border-border/20";

function duration(job: Job) {
  const secs = Math.max(0, Math.round((job.ended ?? Date.now() / 1000) - job.started));
  return secs >= 60 ? `${Math.floor(secs / 60)}m ${String(secs % 60).padStart(2, "0")}s` : `${secs}s`;
}

const POINT = /^\s*(\d{1,4})\s*,\s*(\d{1,4})\s*$/;

function parsePoint(text: string): [number, number] | null {
  const m = POINT.exec(text);
  return m ? [Number(m[1]), Number(m[2])] : null;
}

// The game screen, live from /tools/screen.jpg, for reading a point to click.
// The JPEG is the full-size screen, so image pixels are game pixels. Clicking the
// picture only fills X,Y: the tap itself still takes the Click at X,Y button.
function ScreenPicker({ reloadKey, picked, onPick }: {
  reloadKey: string;
  picked: [number, number] | null;
  onPick: (x: number, y: number) => void;
}) {
  const [opened] = useState(() => Date.now());
  const [refreshes, setRefreshes] = useState(0);
  const [size, setSize] = useState<[number, number] | null>(null);
  const [hover, setHover] = useState<[number, number] | null>(null);
  const [failed, setFailed] = useState(false);

  const src = `${URL}/tools/screen.jpg?v=${opened}-${refreshes}-${encodeURIComponent(reloadKey)}`;

  const toGame = (e: React.MouseEvent<HTMLImageElement>): [number, number] | null => {
    const img = e.currentTarget;
    const rect = img.getBoundingClientRect();
    if (!img.naturalWidth || !rect.width || !rect.height) return null;
    const x = Math.floor(((e.clientX - rect.left) * img.naturalWidth) / rect.width);
    const y = Math.floor(((e.clientY - rect.top) * img.naturalHeight) / rect.height);
    return [Math.min(Math.max(x, 0), img.naturalWidth - 1), Math.min(Math.max(y, 0), img.naturalHeight - 1)];
  };

  const place = (point: [number, number]) =>
    size ? { left: `${(point[0] / size[0]) * 100}%`, top: `${(point[1] / size[1]) * 100}%` } : undefined;

  // Near the right or bottom edge the label flips to the other side of the cursor.
  const flipX = hover && size ? hover[0] > size[0] * 0.85 : false;
  const flipY = hover && size ? hover[1] > size[1] * 0.9 : false;

  return (
    <div className="mt-4">
      <div className="flex flex-wrap items-center gap-3 mb-2">
        <Button size="sm" variant="outline" onClick={() => setRefreshes((n) => n + 1)}>
          <RefreshCw className="size-4" />
          Refresh screen
        </Button>
        <span className="font-mono text-sm text-muted-foreground">
          {hover ? `x ${hover[0]}, y ${hover[1]}` : "Hover the screen to read a point; click it to fill X,Y."}
        </span>
      </div>
      {failed && (
        <div className="mb-2 rounded-lg border border-destructive/40 bg-destructive/10 p-3 font-mono text-sm">
          TOOL-E12 couldn't load the game screen - is main.py running?
        </div>
      )}
      <div className="relative">
        <img
          src={src}
          alt="The game screen"
          draggable={false}
          className="block w-full rounded-lg border border-border cursor-crosshair select-none"
          onLoad={(e) => {
            setFailed(false);
            setSize([e.currentTarget.naturalWidth, e.currentTarget.naturalHeight]);
          }}
          onError={() => setFailed(true)}
          onMouseMove={(e) => setHover(toGame(e))}
          onMouseLeave={() => setHover(null)}
          onClick={(e) => {
            const point = toGame(e);
            if (point) onPick(point[0], point[1]);
          }}
        />
        {picked && size && (
          <span
            className="pointer-events-none absolute size-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary ring-2 ring-background"
            style={place(picked)}
          />
        )}
        {hover && size && (
          <span
            className={`pointer-events-none absolute whitespace-nowrap rounded border border-border bg-popover px-1.5 py-0.5 font-mono text-xs text-popover-foreground shadow ${
              flipX ? "-translate-x-full -ml-3" : "ml-3"
            } ${flipY ? "-translate-y-full -mt-3" : "mt-3"}`}
            style={place(hover)}
          >
            {hover[0]},{hover[1]}
          </span>
        )}
      </div>
    </div>
  );
}

export default function ToolsView() {
  const [status, setStatus] = useState<Status | null>(null);
  // Every failure carries a code: plain words get read as a diagnosis.
  const [fault, setFault] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [at, setAt] = useState("");
  const [text, setText] = useState("");
  const outputRef = useRef<HTMLPreElement>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${URL}/tools/status`, { cache: "no-store" });
      if (!res.ok) throw new Error(`TOOL-E08 the server answered HTTP ${res.status}`);
      setStatus(await res.json());
      setFault(null);
    } catch (e) {
      setFault(e instanceof Error && e.message.startsWith("TOOL-") ? e.message
        : "TOOL-E09 could not reach /tools/status - is main.py running?");
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  const job = status?.job ?? null;
  const lineCount = job?.lines.length ?? 0;
  useEffect(() => {
    if (outputRef.current) outputRef.current.scrollTop = outputRef.current.scrollHeight;
  }, [lineCount]);

  const run = async (tool: Tool, body: Record<string, string> = {}) => {
    if (tool.confirm && !window.confirm(tool.confirm)) return;
    setRefusal(null);
    try {
      const res = await fetch(`${URL}/tools/run/${tool.name}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const detail = await res.json().then((j) => j?.detail).catch(() => null);
        setRefusal(typeof detail === "string" ? detail : `TOOL-E10 the server answered HTTP ${res.status}`);
      }
    } catch {
      setRefusal("TOOL-E09 could not reach /tools/run - is main.py running?");
    }
    refresh();
  };

  const busy = job?.state === "running";
  const botRunning = status?.bot_running ?? false;

  // unready: the tool is missing an input it needs, like a point to click.
  const button = (tool: Tool, body?: Record<string, string>, unready = false) => {
    const locked = !!tool.locked && botRunning;
    const Icon = busy && job?.name === tool.name ? Loader2 : tool.icon;
    return (
      <Button
        key={tool.name}
        variant="outline"
        title={locked ? "Stop the bot first." : unready ? "Pick a point on the screen first." : tool.hint}
        disabled={!status || busy || locked || unready}
        onClick={() => run(tool, body)}
      >
        <Icon className={`size-4 ${Icon === Loader2 ? "animate-spin" : ""}`} />
        {tool.label}
      </Button>
    );
  };

  return (
    <div className="flex flex-col gap-6">
      <div className={CARD}>
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <h2 className="text-3xl font-semibold flex items-center gap-3">
            <Wrench className="text-primary" />
            Tools
          </h2>
          <div className="flex items-center gap-2 text-muted-foreground">
            <span className={`inline-block w-2.5 h-2.5 rounded-full ${botRunning ? "bg-green-600" : "bg-muted-foreground"}`} />
            <span>
              {!status ? "TOOL-E11 no status yet" : botRunning ? "Bot running · clicking tools locked" : "Bot stopped"}
            </span>
          </div>
        </div>

        {fault && <div className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 p-3 font-mono text-sm">{fault}</div>}
        {refusal && (
          <div className="mb-4 rounded-lg border border-amber-500/60 bg-amber-500/5 p-3 font-mono text-sm">{refusal}</div>
        )}

        <div className="flex flex-col gap-6">
          {GROUPS.map((group) => (
            <div key={group.title}>
              <div className="text-xs uppercase tracking-wide text-muted-foreground">{group.title}</div>
              {group.note && <p className="text-sm text-muted-foreground mt-1">{group.note}</p>}
              <div className="flex flex-wrap gap-2 mt-3">{group.tools.map((tool) => button(tool))}</div>
              {group.title === "Career helpers" && (
                <div className="flex flex-wrap items-center gap-2 mt-3">
                  <Dialog>
                    <DialogTrigger asChild>
                      <Button variant="outline" title="Open the game screen, pick a point, then click it">
                        <MousePointerClick className="size-4" />
                        Click on screen
                      </Button>
                    </DialogTrigger>
                    {/* Radix mounts the content only while open, so every opening loads a fresh screenshot. */}
                    <DialogContent className="sm:max-w-[min(96vw,1600px)] max-h-[95vh] overflow-y-auto">
                      <DialogHeader>
                        <DialogTitle>Pick a point</DialogTitle>
                        <DialogDescription>
                          Move over the game screen to read X,Y. Click to set the point. Nothing is tapped until you
                          press Click at X,Y.
                        </DialogDescription>
                      </DialogHeader>
                      <ScreenPicker
                        reloadKey={`${job?.id ?? "none"}:${job?.state ?? "idle"}`}
                        picked={parsePoint(at)}
                        onPick={(x, y) => setAt(`${x},${y}`)}
                      />
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        <span className="mr-auto font-mono text-sm text-muted-foreground">
                          Point: {at || "click the screen to pick one"}
                        </span>
                        {button(CLICK, { at }, !parsePoint(at))}
                        <DialogClose asChild>
                          <Button>Done</Button>
                        </DialogClose>
                      </div>
                    </DialogContent>
                  </Dialog>
                  {/* Typing goes to whatever field is focused, so tap it with Click
                      at X,Y first. Printable ASCII only - the game's keyboard
                      cannot send the rest. */}
                  <Input
                    className="h-9 w-full sm:w-72"
                    placeholder="Text to type into the focused field"
                    maxLength={MAX_TYPE}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                  />
                  {button(TYPE, { text }, !text)}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {job && (
        <div className={CARD}>
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              {job.label} · {job.state}
              {job.exit_code != null && ` · exit ${job.exit_code}`} · {duration(job)}
            </div>
            <code className="text-xs text-muted-foreground break-all">{job.argv.join(" ")}</code>
          </div>
          <pre
            ref={outputRef}
            className="font-mono text-xs leading-relaxed whitespace-pre-wrap break-words max-h-[45vh] overflow-y-auto"
          >
            {job.lines.length ? job.lines.join("\n") : busy ? "Waiting for output..." : "(no output)"}
          </pre>
          {job.image && (
            <a href={`${URL}/tools/shots/${job.image}`} target="_blank" rel="noreferrer" className="block mt-4">
              <img
                src={`${URL}/tools/shots/${job.image}?job=${job.id}`}
                alt={`Screenshot from ${job.label}`}
                className="w-full rounded-lg border border-border"
              />
            </a>
          )}
        </div>
      )}
    </div>
  );
}
