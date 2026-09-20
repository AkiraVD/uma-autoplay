import { useState } from "react";
import { CalendarRange, Loader2, AlertTriangle, Check } from "lucide-react";
import { URL } from "@/constants";

// The planner picks races to earn Trackblazer epithets. Its output is meant to
// be typed into the game's own Agenda screen, which is why OP races are in the
// pool at all: the bot cannot click them (race_select matches
// assets/races/<name>.png and OP races have no picture), but a human entering
// an agenda by hand has no such limit. Anything without a picture is marked,
// and "Use as race schedule" only offers the races the bot could actually run.

const CARD = "bg-card p-5 rounded-xl shadow-lg border border-border/20";

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

type EarnedEpithet = {
  name: string;
  value: number;
  total: number;
  hint: string | null;
};

type PlanResult = {
  schedule: PlannedRace[];
  epithets: EarnedEpithet[];
  missed: Record<string, string>;
  totals: {
    races: number;
    epithets: number;
    epithet_stats: number;
    points: number;
    coins: number;
  };
};

const YEARS = ["Junior Year", "Classic Year", "Senior Year"];
const SURFACES = ["turf", "dirt"];
const DISTANCES = ["sprint", "mile", "medium", "long"];

type Props = {
  onUseSchedule?: (rows: { name: string; year: string; date: string }[]) => void;
};

function RacePlanView({ onUseSchedule }: Props) {
  const [plan, setPlan] = useState<PlanResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [applied, setApplied] = useState(false);
  const [fill, setFill] = useState(false);
  const [limitAptitude, setLimitAptitude] = useState(false);
  const [surfaces, setSurfaces] = useState<string[]>(["turf"]);
  const [distances, setDistances] = useState<string[]>(["mile", "medium"]);

  const toggle = (list: string[], set: (v: string[]) => void, key: string) =>
    set(list.includes(key) ? list.filter((x) => x !== key) : [...list, key]);

  const build = async () => {
    setBusy(true);
    setError(null);
    setApplied(false);
    try {
      // Aptitudes use the same shape as state.APTITUDES: anything not listed is
      // left out, and the planner treats an absent map as "run anything".
      const aptitudes: Record<string, string> = {};
      if (limitAptitude) {
        for (const s of SURFACES) aptitudes[`surface_${s}`] = surfaces.includes(s) ? "a" : "g";
        for (const d of DISTANCES) aptitudes[`distance_${d}`] = distances.includes(d) ? "a" : "g";
      }
      const res = await fetch(`${URL}/data/race_plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fill, aptitudes: limitAptitude ? aptitudes : null }),
      });
      if (!res.ok) throw new Error(`server said ${res.status}`);
      setPlan(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const runnable = plan ? plan.schedule.filter((r) => r.has_image) : [];

  const useSchedule = () => {
    if (!onUseSchedule || !plan) return;
    onUseSchedule(runnable.map(({ name, year, date }) => ({ name, year, date })));
    setApplied(true);
  };

  return (
    <div className="flex flex-col gap-6">
      <h2 className="text-3xl font-semibold flex items-center gap-3">
        <CalendarRange className="h-7 w-7 text-primary" />
        Race Plan
      </h2>

      <div className={CARD}>
        <p className="text-sm text-muted-foreground">
          Picks races that earn Trackblazer epithets, then reports what it could not fit and
          why. Type the result into the game's Agenda screen; the bot only needs to answer the
          race-day notice.
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={fill} onChange={() => setFill(!fill)} />
            Fill spare turns with the best-paying race
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={limitAptitude}
              onChange={() => setLimitAptitude(!limitAptitude)}
            />
            Limit to aptitudes
          </label>
        </div>

        {limitAptitude && (
          <div className="mt-3 flex flex-wrap gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs uppercase tracking-wide text-muted-foreground">Surface</span>
              {SURFACES.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => toggle(surfaces, setSurfaces, s)}
                  className={`rounded-md border px-2 py-0.5 text-xs capitalize ${
                    surfaces.includes(s)
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
                  onClick={() => toggle(distances, setDistances, d)}
                  className={`rounded-md border px-2 py-0.5 text-xs capitalize ${
                    distances.includes(d)
                      ? "bg-primary text-primary-foreground border-primary"
                      : "border-border text-muted-foreground"
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="mt-4 flex items-center gap-3">
          <button
            type="button"
            onClick={build}
            disabled={busy}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60"
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            {busy ? "Planning" : "Build a plan"}
          </button>
          {plan && onUseSchedule && (
            <button
              type="button"
              onClick={useSchedule}
              className="inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 text-sm"
            >
              {applied ? <Check className="h-4 w-4" /> : null}
              {applied ? "Copied to Race Schedule" : `Use ${runnable.length} runnable races`}
            </button>
          )}
        </div>

        {error && (
          <p className="mt-3 flex items-center gap-2 text-sm text-destructive">
            <AlertTriangle className="h-4 w-4" /> {error}
          </p>
        )}
      </div>

      {plan && (
        <>
          <div className={CARD}>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[
                ["Races", plan.totals.races],
                ["Epithets", plan.totals.epithets],
                ["Epithet stats", plan.totals.epithet_stats],
                ["Result Pts", plan.totals.points],
              ].map(([label, value]) => (
                <div key={String(label)}>
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
                  <div className="text-2xl font-semibold tabular-nums">{value}</div>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              Assumes every scheduled race is won, so these are ceilings. Per-race stat and skill
              point gain are not in the game's data, so they are not scored.
            </p>
          </div>

          <div className={CARD}>
            <h3 className="mb-3 text-lg font-semibold">Epithets earned</h3>
            <div className="flex flex-wrap gap-2">
              {plan.epithets.map((e) => (
                <span
                  key={e.name}
                  className="rounded-md border border-border px-2 py-1 text-xs"
                  title={e.hint ? `skill hint: ${e.hint}` : `+${e.value} to 2 stats`}
                >
                  {e.name} <span className="text-muted-foreground">
                    {e.hint ? `hint` : `+${e.value}×2`}
                  </span>
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
            const rows = plan.schedule.filter((r) => r.year === year);
            if (!rows.length) return null;
            return (
              <div key={year} className={CARD}>
                <h3 className="mb-3 text-lg font-semibold">
                  {year} <span className="text-sm text-muted-foreground">({rows.length})</span>
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <tbody>
                      {rows.map((r) => (
                        <tr key={`${r.year}-${r.date}`} className="border-b border-border/30 last:border-0">
                          <td className="py-1 pr-3 whitespace-nowrap text-muted-foreground">{r.date}</td>
                          <td className="py-1 pr-3 whitespace-nowrap">{r.grade}</td>
                          <td className="py-1 pr-3">{r.name}</td>
                          <td className="py-1 pr-3 whitespace-nowrap text-muted-foreground">
                            {r.racetrack} {r.terrain} {r.distance ? `${r.distance.meters}m` : ""}
                          </td>
                          <td className="py-1 text-right">
                            {!r.has_image && (
                              <span
                                className="rounded border border-border px-1.5 py-0.5 text-[10px] uppercase text-muted-foreground"
                                title="No picture asset, so the bot cannot click this race. Fine to enter in the game's Agenda by hand."
                              >
                                agenda only
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
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
