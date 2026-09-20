import { useCallback, useEffect, useRef, useState } from "react";
import { CalendarRange, Loader2, AlertTriangle, Check, Link2, RotateCcw, Save, Trash2 } from "lucide-react";
import { URL } from "@/constants";

// A Trackblazer schedule chosen to earn epithets. Modelled on daftuyda's
// scheduler, but fed from the game's own master.mdb rather than a collected
// JSON file - which is also why there are no stat / skill-point / fan columns:
// master.mdb carries no per-race stat or SP gain, and a made-up number would
// look authoritative. See server/race_plan.py.
//
// OP races are in the pool because the plan is meant to be typed into the
// game's Agenda by hand. The bot cannot click them - race_select matches
// assets/races/<name>.png and OP races have no picture - so anything without a
// picture is marked, and "Use as race schedule" only offers the rest.

const CARD = "bg-card p-5 rounded-xl shadow-lg border border-border/20";
const CHIP = "rounded-md border px-2 py-0.5 text-xs capitalize transition-colors";
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

type SavedList = {
  name: string;
  title: string;
  races: number;
  runnable: number;
  epithets: number;
  saved_at: number;
  unreadable: boolean;
};

const when = (epoch: number) => {
  if (!epoch) return "";
  return new Date(epoch * 1000).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

// No props: this tab is self-contained. It never reads or writes config.json -
// a plan is saved as a named race list, and the Races section loads one from
// there. That way a half-built plan cannot disturb the config the bot is
// running, and the two can be edited from different devices at once.
function RacePlanView() {
  const [settings, setSettings] = useState<Settings>(() => readLink() ?? DEFAULTS);
  const [plan, setPlan] = useState<PlanResult | null>(null);
  const [catalogue, setCatalogue] = useState<EpithetRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [showTargets, setShowTargets] = useState(false);
  const [saved, setSaved] = useState<SavedList[]>([]);
  const [listName, setListName] = useState("");
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);

  const set = <K extends keyof Settings>(key: K, value: Settings[K]) =>
    setSettings((prev) => ({ ...prev, [key]: value }));

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

  // A turn override is the user overruling the solver, so it rebuilds at once.
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

  return (
    <div className="flex flex-col gap-6">
      <h2 className="text-3xl font-semibold flex items-center gap-3">
        <CalendarRange className="h-7 w-7 text-primary" />
        Race Plan
      </h2>

      <div className={CARD}>
        <p className="text-sm text-muted-foreground">
          Picks races that earn Trackblazer epithets, then reports what it could not fit and why.
          Races come from the game's own master.mdb. Type the result into the game's Agenda screen;
          the bot only needs to answer the race-day notice.
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-3">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={settings.fill} onChange={() => set("fill", !settings.fill)} />
            Fill spare turns
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={settings.includeOp}
              onChange={() => set("includeOp", !settings.includeOp)}
            />
            Include OP / Pre-OP races
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={settings.limitAptitude}
              onChange={() => set("limitAptitude", !settings.limitAptitude)}
            />
            Limit to aptitudes
          </label>
          <label className="flex items-center gap-2 text-sm">
            Max races in a row
            <input
              type="number"
              min={0}
              max={59}
              value={settings.maxConsecutive}
              onChange={(e) => set("maxConsecutive", Number(e.target.value))}
              className="h-8 w-16 rounded-md border border-border bg-background px-2 tabular-nums"
            />
            <span className="text-xs text-muted-foreground">0 = no limit</span>
          </label>
        </div>

        {settings.limitAptitude && (
          <div className="mt-3 flex flex-wrap items-center gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs uppercase tracking-wide text-muted-foreground">Surface</span>
              {SURFACES.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => toggle(settings.surfaces, "surfaces", s)}
                  className={`${CHIP} ${
                    settings.surfaces.includes(s)
                      ? "bg-primary text-primary-foreground border-primary"
                      : "border-border text-muted-foreground"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs uppercase tracking-wide text-muted-foreground">Distance</span>
              {DISTANCES.map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => toggle(settings.distances, "distances", d)}
                  className={`${CHIP} ${
                    settings.distances.includes(d)
                      ? "bg-primary text-primary-foreground border-primary"
                      : "border-border text-muted-foreground"
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
            <label className="flex items-center gap-2 text-sm">
              Min aptitude
              <select
                value={settings.minAptitude}
                onChange={(e) => set("minAptitude", e.target.value)}
                className="h-8 rounded-md border border-border bg-background px-2 uppercase"
              >
                {FLOORS.map((f) => (
                  <option key={f} value={f}>
                    {f.toUpperCase()}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}

        <div className="mt-4">
          <button
            type="button"
            onClick={() => setShowTargets(!showTargets)}
            className="text-sm text-muted-foreground underline underline-offset-4"
          >
            {settings.targets.length
              ? `Forced epithets: ${settings.targets.length} chosen`
              : "Forced epithets: none (the solver chooses, scarcest first)"}
          </button>
          {showTargets && (
            <div className="mt-3 flex flex-wrap gap-2">
              {catalogue.map((e) => (
                <button
                  key={e.name}
                  type="button"
                  disabled={!e.selectable}
                  onClick={() => toggle(settings.targets, "targets", e.name)}
                  title={e.why ?? e.condition}
                  className={`${CHIP} normal-case ${
                    settings.targets.includes(e.name)
                      ? "bg-primary text-primary-foreground border-primary"
                      : e.selectable
                        ? "border-border text-muted-foreground"
                        : "border-border/40 text-muted-foreground/40 cursor-not-allowed"
                  }`}
                >
                  {e.name}
                  {e.value ? <span className="ml-1 opacity-70">+{e.value}×2</span> : null}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => build(settings)}
            disabled={busy}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60"
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            {busy ? "Planning" : "Rebuild schedule"}
          </button>
          <button
            type="button"
            onClick={resetOverrides}
            disabled={!overrides}
            className="inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 text-sm disabled:opacity-40"
          >
            <RotateCcw className="h-4 w-4" />
            Reset {overrides || ""} override{overrides === 1 ? "" : "s"}
          </button>
          <button
            type="button"
            onClick={copyLink}
            className="inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 text-sm"
          >
            {copied ? <Check className="h-4 w-4" /> : <Link2 className="h-4 w-4" />}
            {copied ? "Link copied" : "Copy link"}
          </button>
        </div>

        {error && (
          <p className="mt-3 flex items-center gap-2 text-sm text-destructive">
            <AlertTriangle className="h-4 w-4" /> {error}
          </p>
        )}
      </div>

      <div className={CARD}>
        <h3 className="text-lg font-semibold">Saved race lists</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Kept in <code>uma_race_lists/</code> beside the bot, so the same lists show up on every
          device. The Races section of the Configuration tab loads one into the bot's schedule —
          nothing here changes the config by itself.
        </p>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input
            aria-label="Name for this race list"
            placeholder="name for this race list"
            value={listName}
            onChange={(e) => setListName(e.target.value)}
            className="h-9 min-w-52 flex-1 rounded-md border border-border bg-background px-3 text-sm"
          />
          <button
            type="button"
            onClick={saveList}
            disabled={!plan || !target || busy}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            {overwrites ? "Overwrite" : "Save"} {plan ? `${plan.schedule.length} races` : ""}
          </button>
        </div>
        {target && (
          <p className="mt-2 text-xs text-muted-foreground">
            Saves as <code>uma_race_lists/{target}.json</code>
            {overwrites && " — replacing the list already there."}
            {plan && runnable.length < plan.schedule.length && (
              <> · {plan.schedule.length - runnable.length} of these are agenda-only, so the
              Races section will load {runnable.length}.</>
            )}
          </p>
        )}
        {savedMsg && (
          <p className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
            <Check className="h-4 w-4" /> {savedMsg}
          </p>
        )}

        <div className="mt-4 rounded-lg border border-border">
          {saved.length === 0 ? (
            <p className="px-3 py-6 text-center text-sm text-muted-foreground">
              Nothing saved yet.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {saved.map((s) => (
                <li key={s.name} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">
                      {s.title}
                      {s.unreadable && (
                        <span className="ml-2 text-xs font-normal text-destructive">unreadable</span>
                      )}
                    </div>
                    <div className="truncate text-xs text-muted-foreground">
                      {s.races} races · {s.runnable} runnable · {s.epithets} epithets
                      <span className="ml-2 opacity-70">{when(s.saved_at)}</span>
                    </div>
                  </div>
                  {confirming === s.name ? (
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-muted-foreground">Delete?</span>
                      <button
                        type="button"
                        onClick={() => {
                          deleteList(s.name);
                          setConfirming(null);
                        }}
                        className="rounded-md border border-destructive px-2 py-1 text-destructive"
                      >
                        Yes
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
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        disabled={s.unreadable || busy}
                        onClick={() => loadList(s.name)}
                        className="rounded-md border border-border px-3 py-1 text-xs disabled:opacity-40"
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
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
                  <div className="text-2xl font-semibold tabular-nums">{value}</div>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              Assumes every scheduled race is won, so these are ceilings. Per-race stat and
              skill-point gain are not in the game's data, so no race is scored or ranked — only
              the epithets a schedule earns decide anything.
            </p>
          </div>

          <div className={CARD}>
            <h3 className="mb-3 text-lg font-semibold">Epithets from this schedule</h3>
            <div className="flex flex-wrap gap-2">
              {plan.progress.map((e) => (
                <span
                  key={e.name}
                  title={e.condition || undefined}
                  className={`rounded-md border px-2 py-1 text-xs ${
                    e.earned ? "border-primary text-foreground" : "border-border text-muted-foreground"
                  }`}
                >
                  {e.name}{" "}
                  <span className="tabular-nums opacity-70">
                    {e.have}/{e.need}
                  </span>
                  {e.earned && <span className="ml-1">{e.hint ? "hint" : `+${e.value}×2`}</span>}
                </span>
              ))}
            </div>

            {Object.keys(plan.missed).length > 0 && (
              <>
                <h3 className="mb-2 mt-5 text-lg font-semibold">Not fitted, and why</h3>
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
                <h3 className="mb-3 text-lg font-semibold">
                  {year}{" "}
                  <span className="text-sm text-muted-foreground">
                    ({raced} of {rows.length} turns raced)
                  </span>
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <tbody>
                      {rows.map((turn) => {
                        const race = turn.options.find((o) => o.name === turn.picked);
                        return (
                          <tr key={turn.key} className="border-b border-border/30 last:border-0">
                            <td className="w-24 py-1 pr-3 whitespace-nowrap text-muted-foreground">
                              {turn.date}
                            </td>
                            <td className="w-12 py-1 pr-3 whitespace-nowrap">{race?.grade ?? ""}</td>
                            <td className="py-1 pr-3">
                              <select
                                value={turnValue(turn)}
                                onChange={(e) => setTurn(turn.key, e.target.value)}
                                disabled={busy}
                                className={`h-8 w-full max-w-xs rounded-md border bg-background px-2 ${
                                  turnValue(turn) === AUTO
                                    ? "border-border/40"
                                    : "border-primary"
                                }`}
                              >
                                <option value={AUTO}>
                                  {turn.picked ? `Auto — ${turn.picked}` : "Auto — no race"}
                                </option>
                                <option value={NONE}>No race</option>
                                {turn.options.map((o) => (
                                  <option key={o.name} value={o.name}>
                                    {o.name}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td className="py-1 pr-3 whitespace-nowrap text-muted-foreground">
                              {race
                                ? `${race.racetrack ?? ""} ${race.terrain ?? ""} ${
                                    race.distance ? `${race.distance.meters}m` : ""
                                  }`
                                : ""}
                            </td>
                            <td className="py-1 text-right whitespace-nowrap">
                              {turn.pinned && (
                                <span
                                  className="mr-1 rounded border border-border px-1.5 py-0.5 text-[10px] uppercase text-muted-foreground"
                                  title="An epithet depends on this turn, or you pinned it. Never thinned away."
                                >
                                  pinned
                                </span>
                              )}
                              {race && !race.has_image && (
                                <span
                                  className="rounded border border-border px-1.5 py-0.5 text-[10px] uppercase text-muted-foreground"
                                  title="No picture asset, so the bot cannot click this race. Fine to enter in the game's Agenda by hand."
                                >
                                  agenda only
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}

export default RacePlanView;
