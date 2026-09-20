import { useCallback, useEffect, useRef, useState } from "react";
import {
  CalendarRange, Loader2, AlertTriangle, Check, Link2, RotateCcw, Save, Trash2, Search, Pin,
} from "lucide-react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { URL } from "@/constants";

// A Trackblazer schedule chosen to earn epithets. Modelled on daftuyda's
// scheduler, but fed from the game's own master.mdb rather than a collected
// JSON file - which is also why there are no stat / skill-point / fan columns:
// master.mdb carries no per-race stat or SP gain, and a made-up number would
// look authoritative. See server/race_plan.py.
//
// OP races are in the pool because a plan is meant to be typed into the game's
// Agenda by hand. The bot cannot click them - race_select matches
// assets/races/<name>.png and OP races have no picture - so those are marked
// "agenda only" and the Races section filters them out when it loads a list.
//
// Layout: settings live in a sticky sidebar, results and the turn grid on the
// right. The grid is 59 rows, so anything that scrolls away with it is
// effectively gone - which is why no control is hidden behind a disclosure.
// An aptitude filter that is switched off is shown disabled rather than
// removed, so it can still be found.

const CARD = "bg-card p-5 rounded-xl shadow-lg border border-border/20";
const LABEL = "text-xs font-semibold uppercase tracking-wide text-muted-foreground";
const CHIP = "rounded-md border px-2.5 py-1 text-xs capitalize transition-colors disabled:cursor-not-allowed";
const ON = "bg-primary text-primary-foreground border-primary";
const OFF = "border-border text-muted-foreground hover:border-primary/60";
const AUTO = "__auto__";
const NONE = "__none__";

type Distance = { type: string; meters: number };

type PlannedRace = {
  name: string;
  year: string;
  date: string;
  grade: string | null;
  racetrack: string | null;
  terrain: string | null;
  distance: Distance | null;
  has_image: boolean;
};

type Turn = {
  key: string;
  year: string;
  date: string;
  picked: string | null;
  pinned: boolean;
  skipped: boolean;
  options: PlannedRace[];
};

type EarnedEpithet = { name: string; value: number; total: number; hint: string | null };

type Progress = {
  name: string;
  have: number;
  need: number;
  earned: boolean;
  value: number;
  hint: string | null;
  condition: string;
};

type PlanResult = {
  schedule: PlannedRace[];
  turns: Turn[];
  epithets: EarnedEpithet[];
  progress: Progress[];
  missed: Record<string, string>;
  totals: {
    races: number;
    epithets: number;
    epithet_stats: number;
    points: number;
    coins: number;
    longest_run: number;
  };
};

type EpithetRow = {
  name: string;
  value: number;
  hint: string | null;
  condition: string;
  selectable: boolean;
  why: string | null;
};

type SavedList = {
  name: string;
  title: string;
  races: number;
  runnable: number;
  epithets: number;
  saved_at: number;
  unreadable: boolean;
};

const YEARS = ["Junior Year", "Classic Year", "Senior Year"];
const SURFACES = ["turf", "dirt"];
const DISTANCES = ["sprint", "mile", "medium", "long"];
const FLOORS = ["s", "a", "b", "c", "d", "e", "f", "g"];

// Everything the share link carries. Kept as one object so the link and the
// state stay in step by construction.
type Settings = {
  fill: boolean;
  includeOp: boolean;
  limitAptitude: boolean;
  surfaces: string[];
  distances: string[];
  minAptitude: string;
  maxConsecutive: number;
  targets: string[];
  locks: Record<string, string>;
  skip: string[];
};

const DEFAULTS: Settings = {
  fill: true,
  includeOp: true,
  limitAptitude: false,
  surfaces: ["turf"],
  distances: ["mile", "medium"],
  minAptitude: "b",
  maxConsecutive: 3,
  targets: [],
  locks: {},
  skip: [],
};

function readLink(): Settings | null {
  const hash = window.location.hash;
  if (!hash.startsWith("#plan=")) return null;
  try {
    return { ...DEFAULTS, ...JSON.parse(atob(decodeURIComponent(hash.slice(6)))) };
  } catch {
    return null;
  }
}

const when = (epoch: number) => {
  if (!epoch) return "";
  return new Date(epoch * 1000).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

function Section({ title, hint, children }: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-t border-border/60 pt-4 first:border-0 first:pt-0">
      <h3 className={LABEL}>{title}</h3>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      <div className="mt-2.5">{children}</div>
    </section>
  );
}

function Toggle({ checked, onChange, children }: {
  checked: boolean;
  onChange: () => void;
  children: React.ReactNode;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2.5 py-1 text-sm">
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="h-4 w-4 shrink-0 accent-[var(--primary)]"
      />
      <span>{children}</span>
    </label>
  );
}

// No props: this tab is self-contained. It never reads or writes config.json -
// a plan is saved as a named race list, and the Races section loads one from
// there. That way a half-built plan cannot disturb the config the bot is
// running, and the two can be edited from different devices at once.
function RacePlanView() {
  const [settings, setSettings] = useState<Settings>(() => readLink() ?? DEFAULTS);
  const [plan, setPlan] = useState<PlanResult | null>(null);
  const [catalogue, setCatalogue] = useState<EpithetRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [epithetSearch, setEpithetSearch] = useState("");
  const [saved, setSaved] = useState<SavedList[]>([]);
  const [listName, setListName] = useState("");
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);

  // Every settings change marks the plan stale rather than rebuilding on each
  // keystroke. Without this, ticking a distance appeared to do nothing at all -
  // the plan on screen still came from the previous settings.
  const set = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setDirty(true);
  };

  const toggle = (list: string[], key: keyof Settings, value: string) =>
    set(key, (list.includes(value)
      ? list.filter((x) => x !== value)
      : [...list, value]) as Settings[typeof key]);

  const build = useCallback(async (current: Settings) => {
    setBusy(true);
    setError(null);
    setSavedMsg(null);
    try {
      // Aptitudes use the same shape as state.APTITUDES: anything not listed is
      // left out, and the planner treats an absent map as "run anything".
      const aptitudes: Record<string, string> = {};
      if (current.limitAptitude) {
        for (const s of SURFACES) aptitudes[`surface_${s}`] = current.surfaces.includes(s) ? "a" : "g";
        for (const d of DISTANCES) aptitudes[`distance_${d}`] = current.distances.includes(d) ? "a" : "g";
      }
      const res = await fetch(`${URL}/data/race_plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fill: current.fill,
          include_op: current.includeOp,
          min_aptitude: current.minAptitude,
          max_consecutive: current.maxConsecutive,
          targets: current.targets.length ? current.targets : null,
          locks: current.locks,
          skip: current.skip,
          aptitudes: current.limitAptitude ? aptitudes : null,
        }),
      });
      if (!res.ok) throw new Error(`server said ${res.status}`);
      setPlan(await res.json());
      setDirty(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  const refreshSaved = useCallback(async () => {
    try {
      const res = await fetch(`${URL}/race_lists`);
      setSaved(res.ok ? await res.json() : []);
    } catch {
      setSaved([]);
    }
  }, []);

  // One plan on arrival, so the page opens showing what it does rather than an
  // empty shell. The ref keeps a settings change from firing a second build
  // before the first has landed.
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    build(settings);
    refreshSaved();
    fetch(`${URL}/data/epithets`)
      .then((r) => r.json())
      .then((d) => setCatalogue(d.epithets ?? []))
      .catch(() => setCatalogue([]));
  }, [build, refreshSaved, settings]);

  // A turn override is the user overruling the solver on one turn, so it takes
  // effect at once - unlike a settings change, there is nothing else to batch.
  const setTurn = (turnKey: string, value: string) => {
    const locks = { ...settings.locks };
    const skip = settings.skip.filter((k) => k !== turnKey);
    delete locks[turnKey];
    if (value === NONE) skip.push(turnKey);
    else if (value !== AUTO) locks[turnKey] = value;
    const next = { ...settings, locks, skip };
    setSettings(next);
    build(next);
  };

  const resetOverrides = () => {
    const next = { ...settings, locks: {}, skip: [] };
    setSettings(next);
    build(next);
  };

  const copyLink = async () => {
    const hash = `#plan=${encodeURIComponent(btoa(JSON.stringify(settings)))}`;
    const link = `${window.location.origin}${window.location.pathname}${hash}`;
    window.history.replaceState(null, "", hash);
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("couldn't reach the clipboard; the address bar now holds the link");
    }
  };

  const runnable = plan ? plan.schedule.filter((r) => r.has_image) : [];
  const overrides = Object.keys(settings.locks).length + settings.skip.length;
  const target = listName.trim();
  const overwrites = saved.some((s) => s.name === target);

  // The whole schedule is saved, agenda-only races included, because the list
  // is also what gets typed into the game by hand. The Races section filters to
  // the runnable ones when it loads, since those are all the bot can click.
  const saveList = async () => {
    if (!plan || !target) return;
    setError(null);
    try {
      const res = await fetch(`${URL}/race_lists/${encodeURIComponent(target)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: target,
          races: plan.schedule,
          settings,
          epithets: plan.epithets.map((e) => e.name),
        }),
      });
      if (!res.ok) throw new Error((await res.json()).detail ?? `server said ${res.status}`);
      const out = await res.json();
      setSavedMsg(`Saved "${out.name}" — ${out.races} races`);
      setListName("");
      refreshSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  // Loading restores the settings that produced the plan, then rebuilds, so a
  // saved list reopens as a working plan rather than a frozen table.
  const loadList = async (name: string) => {
    setError(null);
    try {
      const res = await fetch(`${URL}/race_lists/${encodeURIComponent(name)}`);
      if (!res.ok) throw new Error((await res.json()).detail ?? `server said ${res.status}`);
      const data = await res.json();
      const next = { ...DEFAULTS, ...(data.settings ?? {}) };
      setSettings(next);
      setListName(name);
      setSavedMsg(`Loaded "${data.title || name}"`);
      build(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const deleteList = async (name: string) => {
    setError(null);
    try {
      const res = await fetch(`${URL}/race_lists/${encodeURIComponent(name)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error((await res.json()).detail ?? `server said ${res.status}`);
      setSavedMsg(`Deleted "${name}"`);
      refreshSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const turnValue = (turn: Turn) =>
    settings.locks[turn.key] ?? (settings.skip.includes(turn.key) ? NONE : AUTO);

  const apt = settings.limitAptitude;
  const query = epithetSearch.trim().toLowerCase();
  const epithets = catalogue.filter(
    (e) => !query || e.name.toLowerCase().includes(query) || e.condition.toLowerCase().includes(query)
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="flex items-center gap-3 text-3xl font-semibold">
          <CalendarRange className="h-7 w-7 text-primary" />
          Race Plan
        </h2>
        <p className="text-sm text-muted-foreground">
          Races that earn Trackblazer epithets, from the game's own master.mdb.
        </p>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[23rem_minmax(0,1fr)]">
        {/* ---------------------------------------------------------- SETTINGS */}
        <div className="flex flex-col gap-4 lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto lg:pr-1">
          <div className={`${CARD} flex flex-col gap-4`}>
            <Section
              title="Trainee aptitudes"
              hint={apt ? undefined : "Off: every race is considered, whatever she can run."}
            >
              <Toggle checked={apt} onChange={() => set("limitAptitude", !apt)}>
                Only races she can run
              </Toggle>

              <div className={`mt-3 flex flex-col gap-3 ${apt ? "" : "opacity-40"}`}>
                <div>
                  <div className="mb-1.5 text-xs text-muted-foreground">Surface</div>
                  <div className="flex flex-wrap gap-1.5">
                    {SURFACES.map((s) => (
                      <button
                        key={s}
                        type="button"
                        disabled={!apt}
                        onClick={() => toggle(settings.surfaces, "surfaces", s)}
                        className={`${CHIP} ${settings.surfaces.includes(s) ? ON : OFF}`}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="mb-1.5 text-xs text-muted-foreground">Distance</div>
                  <div className="flex flex-wrap gap-1.5">
                    {DISTANCES.map((d) => (
                      <button
                        key={d}
                        type="button"
                        disabled={!apt}
                        onClick={() => toggle(settings.distances, "distances", d)}
                        className={`${CHIP} ${settings.distances.includes(d) ? ON : OFF}`}
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                </div>

                <label className="flex items-center justify-between gap-2 text-sm">
                  <span className="text-muted-foreground">Lowest aptitude she'll run</span>
                  <select
                    value={settings.minAptitude}
                    disabled={!apt}
                    onChange={(e) => set("minAptitude", e.target.value)}
                    className="h-8 rounded-md border border-border bg-background px-2 uppercase disabled:cursor-not-allowed"
                  >
                    {FLOORS.map((f) => (
                      <option key={f} value={f}>{f.toUpperCase()}</option>
                    ))}
                  </select>
                </label>
              </div>
            </Section>

            <Section title="Race pool">
              <Toggle checked={settings.includeOp} onChange={() => set("includeOp", !settings.includeOp)}>
                Include OP / Pre-OP races
              </Toggle>
              <Toggle checked={settings.fill} onChange={() => set("fill", !settings.fill)}>
                Fill spare turns
              </Toggle>
              <label className="mt-2 flex items-center justify-between gap-2 text-sm">
                <span className="text-muted-foreground">Max races in a row</span>
                <input
                  type="number"
                  min={0}
                  max={59}
                  value={settings.maxConsecutive}
                  onChange={(e) => set("maxConsecutive", Number(e.target.value))}
                  className="h-8 w-16 rounded-md border border-border bg-background px-2 text-right tabular-nums"
                />
              </label>
              <p className="mt-1 text-xs text-muted-foreground">
                0 removes the limit. A turn an epithet needs is never broken, so a run can still
                exceed this — the real figure is in Longest run.
              </p>
            </Section>

            <Section
              title={`Target epithets${settings.targets.length ? ` · ${settings.targets.length}` : ""}`}
              hint={settings.targets.length
                ? undefined
                : "None chosen: the solver takes the scarcest first."}
            >
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={epithetSearch}
                  onChange={(e) => setEpithetSearch(e.target.value)}
                  placeholder="Find an epithet or condition..."
                  className="h-8 pl-8 text-sm"
                />
              </div>
              {settings.targets.length > 0 && (
                <button
                  type="button"
                  onClick={() => set("targets", [])}
                  className="mt-2 text-xs text-muted-foreground underline underline-offset-4"
                >
                  Clear {settings.targets.length} chosen
                </button>
              )}
              <div className="mt-2 max-h-56 overflow-y-auto rounded-md border border-border p-2">
                <div className="flex flex-wrap gap-1.5">
                  {epithets.length === 0 && (
                    <p className="px-1 py-2 text-xs text-muted-foreground">Nothing matches.</p>
                  )}
                  {epithets.map((e) => (
                    <button
                      key={e.name}
                      type="button"
                      disabled={!e.selectable}
                      onClick={() => toggle(settings.targets, "targets", e.name)}
                      title={e.why ?? e.condition}
                      className={`${CHIP} normal-case ${
                        settings.targets.includes(e.name)
                          ? ON
                          : e.selectable
                            ? OFF
                            : "border-border/40 text-muted-foreground/40"
                      }`}
                    >
                      {e.name}
                      {e.value ? <span className="ml-1 opacity-70">+{e.value}×2</span> : null}
                      {e.hint ? <span className="ml-1 opacity-70">hint</span> : null}
                    </button>
                  ))}
                </div>
              </div>
            </Section>
          </div>

          {/* Actions sit outside the scrolling settings card so Rebuild is always
              reachable, and the stale hint is next to the button that clears it. */}
          <div className={`${CARD} flex flex-col gap-2`}>
            <Button
              onClick={() => build(settings)}
              disabled={busy}
              className={`w-full ${dirty ? "" : "opacity-90"}`}
            >
              {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {busy ? "Planning" : dirty ? "Apply changes" : "Rebuild schedule"}
            </Button>
            {dirty && !busy && (
              <p className="text-center text-xs text-primary">
                Settings changed — the plan below is from the previous ones.
              </p>
            )}
            <div className="flex gap-2">
              <Button
                variant="outline"
                className="flex-1"
                onClick={resetOverrides}
                disabled={!overrides}
                title="Clear every pinned turn and every 'No race' you set"
              >
                <RotateCcw className="mr-2 h-4 w-4" />
                {overrides ? `Reset ${overrides}` : "No overrides"}
              </Button>
              <Button variant="outline" className="flex-1" onClick={copyLink}>
                {copied ? <Check className="mr-2 h-4 w-4" /> : <Link2 className="mr-2 h-4 w-4" />}
                {copied ? "Copied" : "Copy link"}
              </Button>
            </div>
            {error && (
              <p className="flex items-start gap-2 text-sm text-destructive">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
              </p>
            )}
          </div>

          {/* --------------------------------------------------- SAVED LISTS */}
          <div className={CARD}>
            <h3 className={LABEL}>Saved race lists</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              Kept in <code>uma_race_lists/</code>, so the same lists appear on every device. The
              Races section loads one; nothing here changes the config by itself.
            </p>

            <div className="mt-3 flex gap-2">
              <Input
                aria-label="Name for this race list"
                placeholder="name this list"
                value={listName}
                onChange={(e) => setListName(e.target.value)}
                className="h-9 flex-1"
              />
              <Button onClick={saveList} disabled={!plan || !target || busy}>
                <Save className="mr-2 h-4 w-4" />
                {overwrites ? "Overwrite" : "Save"}
              </Button>
            </div>
            {target && plan && (
              <p className="mt-2 text-xs text-muted-foreground">
                Saves {plan.schedule.length} races as <code>{target}.json</code>
                {overwrites && " — replacing the list already there."}
                {runnable.length < plan.schedule.length &&
                  ` · ${plan.schedule.length - runnable.length} are agenda-only, so the Races
                    section will load ${runnable.length}.`}
              </p>
            )}
            {savedMsg && (
              <p className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                <Check className="h-3.5 w-3.5" /> {savedMsg}
              </p>
            )}

            <div className="mt-3 rounded-lg border border-border">
              {saved.length === 0 ? (
                <p className="px-3 py-5 text-center text-xs text-muted-foreground">
                  Nothing saved yet.
                </p>
              ) : (
                <ul className="divide-y divide-border">
                  {saved.map((s) => (
                    <li key={s.name} className="flex items-center gap-2 px-3 py-2">
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium">
                          {s.title}
                          {s.unreadable && (
                            <span className="ml-2 text-xs font-normal text-destructive">
                              unreadable
                            </span>
                          )}
                        </div>
                        <div className="truncate text-xs text-muted-foreground">
                          {s.races} races · {s.runnable} runnable · {s.epithets} epithets
                          <span className="ml-2 opacity-70">{when(s.saved_at)}</span>
                        </div>
                      </div>
                      {confirming === s.name ? (
                        <div className="flex shrink-0 items-center gap-1 text-xs">
                          <button
                            type="button"
                            onClick={() => {
                              deleteList(s.name);
                              setConfirming(null);
                            }}
                            className="rounded-md border border-destructive px-2 py-1 text-destructive"
                          >
                            Delete
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirming(null)}
                            className="rounded-md px-2 py-1 text-muted-foreground"
                          >
                            No
                          </button>
                        </div>
                      ) : (
                        <div className="flex shrink-0 items-center gap-1">
                          <button
                            type="button"
                            disabled={s.unreadable || busy}
                            onClick={() => loadList(s.name)}
                            className="rounded-md border border-border px-2.5 py-1 text-xs disabled:opacity-40"
                          >
                            Load
                          </button>
                          <button
                            type="button"
                            aria-label={`Delete ${s.title}`}
                            onClick={() => setConfirming(s.name)}
                            className="rounded-md p-1 text-muted-foreground hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>

        {/* ----------------------------------------------------------- RESULTS */}
        <div className={`flex flex-col gap-6 ${dirty ? "opacity-70" : ""}`}>
          {!plan && (
            <div className={`${CARD} flex items-center gap-3 text-sm text-muted-foreground`}>
              <Loader2 className="h-4 w-4 animate-spin" /> Building the first plan…
            </div>
          )}

          {plan && (
            <>
              <div className={CARD}>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
                  {[
                    ["Races", plan.totals.races],
                    ["Epithets", plan.totals.epithets],
                    ["Epithet stats", plan.totals.epithet_stats],
                    ["Result Pts", plan.totals.points],
                    ["Longest run", plan.totals.longest_run],
                  ].map(([label, value]) => (
                    <div key={String(label)}>
                      <div className={LABEL}>{label}</div>
                      <div className="text-2xl font-semibold tabular-nums">{value}</div>
                    </div>
                  ))}
                </div>
                <p className="mt-3 text-xs text-muted-foreground">
                  Assumes every scheduled race is won, so these are ceilings. Per-race stat and
                  skill-point gain are not in the game's data, so no race is scored or ranked —
                  only the epithets a schedule earns decide anything.
                </p>
              </div>

              <div className={CARD}>
                <div className="mb-3 flex items-baseline justify-between gap-2">
                  <h3 className="text-lg font-semibold">Epithets</h3>
                  <span className="text-xs text-muted-foreground">
                    {plan.totals.epithets} earned · {plan.progress.length - plan.totals.epithets} partial
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {plan.progress.map((e) => (
                    <span
                      key={e.name}
                      title={e.condition || undefined}
                      className={`rounded-md border px-2 py-1 text-xs ${
                        e.earned
                          ? "border-primary bg-primary/10 text-foreground"
                          : "border-border text-muted-foreground"
                      }`}
                    >
                      {e.name}{" "}
                      <span className="tabular-nums opacity-70">{e.have}/{e.need}</span>
                      {e.earned && <span className="ml-1">{e.hint ? "hint" : `+${e.value}×2`}</span>}
                    </span>
                  ))}
                </div>

                {Object.keys(plan.missed).length > 0 && (
                  <>
                    <h4 className={`${LABEL} mb-2 mt-5`}>Not fitted, and why</h4>
                    <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
                      {Object.entries(plan.missed).map(([name, why]) => (
                        <li key={name}>
                          <span className="text-foreground">{name}</span> — {why}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>

              {YEARS.map((year) => {
                const rows = plan.turns.filter((t) => t.year === year);
                if (!rows.length) return null;
                const raced = rows.filter((t) => t.picked).length;
                return (
                  <div key={year} className={CARD}>
                    <div className="mb-3 flex items-baseline justify-between gap-2">
                      <h3 className="text-lg font-semibold">{year}</h3>
                      <span className="text-xs text-muted-foreground">
                        {raced} of {rows.length} turns raced
                      </span>
                    </div>
                    <div className="flex flex-col">
                      {rows.map((turn) => {
                        const race = turn.options.find((o) => o.name === turn.picked);
                        const overridden = turnValue(turn) !== AUTO;
                        return (
                          <div
                            key={turn.key}
                            className={`flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border/30 py-1.5 last:border-0 ${
                              race ? "" : "opacity-60"
                            }`}
                          >
                            <span className="w-20 shrink-0 text-xs text-muted-foreground">
                              {turn.date}
                            </span>
                            <span className="w-9 shrink-0 text-xs font-medium">
                              {race?.grade ?? ""}
                            </span>
                            <select
                              value={turnValue(turn)}
                              onChange={(e) => setTurn(turn.key, e.target.value)}
                              disabled={busy}
                              className={`h-8 min-w-0 flex-1 rounded-md border bg-background px-2 text-sm ${
                                overridden ? "border-primary" : "border-border/40"
                              }`}
                            >
                              <option value={AUTO}>
                                {turn.picked ? `Auto — ${turn.picked}` : "Auto — no race"}
                              </option>
                              <option value={NONE}>No race</option>
                              {turn.options.map((o) => (
                                <option key={o.name} value={o.name}>{o.name}</option>
                              ))}
                            </select>
                            <span className="hidden w-52 shrink-0 truncate text-xs text-muted-foreground sm:block">
                              {race
                                ? [race.racetrack, race.terrain,
                                   race.distance ? `${race.distance.meters}m` : null]
                                    .filter(Boolean).join(" · ")
                                : ""}
                            </span>
                            <span className="flex shrink-0 items-center gap-1">
                              {turn.pinned && (
                                <Pin
                                  className="h-3.5 w-3.5 text-primary"
                                  aria-label="pinned"
                                />
                              )}
                              {race && !race.has_image && (
                                <span
                                  className="rounded border border-border px-1.5 py-0.5 text-[10px] uppercase text-muted-foreground"
                                  title="No picture asset, so the bot cannot click this race. Fine to enter in the game's Agenda by hand."
                                >
                                  agenda
                                </span>
                              )}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default RacePlanView;
