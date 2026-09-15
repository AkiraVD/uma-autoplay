import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import { Input } from "../ui/input";
import { CalendarDays, Check, Search, X } from "lucide-react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { URL } from "@/constants";
import type { RaceScheduleType } from "@/types";
// Built in as a fallback for a server that predates /data/races.
import racesData from "../../../../data/races.json";

type RaceType = {
  date: string;
  racetrack: string;
  terrain: string;
  distance: {
    type: string;
    meters: number;
  };
  sparks: string[];
  fans: {
    required: number;
    gained: number;
  };
  grade?: string;
  // The bot picks a race by assets/races/<name>.png; without one it can't.
  has_image?: boolean;
};

type RaceData = {
  source: string;
  races: Record<string, Record<string, RaceType>>;
};

const FALLBACK: RaceData = {
  source: "built-in races.json",
  races: racesData as Record<string, Record<string, RaceType>>,
};
const YEARS = ["Junior Year", "Classic Year", "Senior Year"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DISTANCES = ["Sprint", "Mile", "Medium", "Long"];
const TERRAINS = ["Turf", "Dirt"];
const GRADES = ["G1", "G2", "G3"];

// The server reads the game's master.mdb (server/master_data.py).
// Throws on failure (an old server answers with the page, which isn't JSON), so
// the query retries; the built-in list only stands in while there's no answer.
const getRaceData = async (): Promise<RaceData> => {
  const res = await fetch(`${URL}/data/races`);
  if (!res.ok) throw new Error(`RACES-FETCH: HTTP ${res.status}`);
  return await res.json();
};

// An empty set means "all": nothing picked in a group filters nothing out.
const toggleIn = (list: string[], value: string) =>
  list.includes(value) ? list.filter((v) => v !== value) : [...list, value];

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-2.5 py-0.5 rounded-lg border text-sm transition-colors ${
        active
          ? "bg-primary text-primary-foreground border-primary"
          : "bg-transparent border-border/60 hover:border-primary"
      }`}
    >
      {children}
    </button>
  );
}

function ChipGroup({ label, options, selected, setSelected, format = (v) => v }: {
  label: string;
  options: string[];
  selected: string[];
  setSelected: (value: string[]) => void;
  format?: (value: string) => string;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-sm text-muted-foreground mr-1">{label}</span>
      {options.map((o) => (
        <Chip key={o} active={selected.includes(o)} onClick={() => setSelected(toggleIn(selected, o))}>
          {format(o)}
        </Chip>
      ))}
    </div>
  );
}

// "Early Dec" -> a number that sorts in calendar order within a year.
const turnOrder = (year: string, date: string) => {
  const [half, month] = date.split(" ");
  return YEARS.indexOf(year) * 100 + MONTHS.indexOf(month) * 2 + (half === "Late" ? 1 : 0);
};

type Props = {
  raceSchedule: RaceScheduleType[];
  addRaceSchedule: (newList: RaceScheduleType) => void;
  deleteRaceSchedule: (name: string, year: string) => void;
  clearRaceSchedule: () => void;
};

export default function RaceSchedule({
  raceSchedule,
  addRaceSchedule,
  deleteRaceSchedule,
  clearRaceSchedule,
}: Props) {
  const isScheduled = (name: string, year: string) =>
    raceSchedule.some((race) => race.name === name && race.year === year);

  const toggle = (name: string, year: string, date: string) => {
    if (isScheduled(name, year)) deleteRaceSchedule(name, year);
    else addRaceSchedule({ name, date, year });
  };

  const scheduled = [...raceSchedule].sort(
    (a, b) => turnOrder(a.year, a.date) - turnOrder(b.year, b.date)
  );

  const { data = FALLBACK } = useQuery<RaceData>({
    queryKey: ["races"],
    queryFn: getRaceData,
  });
  const RACES = data.races;
  const pickable = (detail: RaceType) => detail.has_image !== false;

  const [search, setSearch] = useState("");
  const [years, setYears] = useState<string[]>([]);
  const [grades, setGrades] = useState<string[]>([]);
  const [distances, setDistances] = useState<string[]>([]);
  const [terrains, setTerrains] = useState<string[]>([]);
  const [pickableOnly, setPickableOnly] = useState(true);
  const filtering = search !== "" || years.length > 0 || grades.length > 0 || distances.length > 0 || terrains.length > 0 || !pickableOnly;
  const resetFilters = () => {
    setSearch("");
    setYears([]);
    setGrades([]);
    setDistances([]);
    setTerrains([]);
    setPickableOnly(true);
  };

  const query = search.trim().toLowerCase();
  const visible = YEARS.filter((year) => RACES[year] && (years.length === 0 || years.includes(year)))
    .map((year) => ({
      year,
      races: Object.entries(RACES[year]).filter(([name, detail]) =>
        (!pickableOnly || pickable(detail)) &&
        (grades.length === 0 || grades.includes(detail.grade ?? "G1")) &&
        (distances.length === 0 || distances.includes(detail.distance.type)) &&
        (terrains.length === 0 || terrains.includes(detail.terrain)) &&
        (query === "" || name.toLowerCase().includes(query) || detail.racetrack.toLowerCase().includes(query))
      ),
    }))
    .filter(({ races }) => races.length > 0);
  const unpickable = Object.values(RACES).reduce((n, year) => n + Object.values(year).filter((d) => !pickable(d)).length, 0);
  const visibleCount = visible.reduce((n, { races }) => n + races.length, 0);

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button className="w-fit flex items-center gap-2">
          <CalendarDays className="w-4 h-4" />
          Select Race
          {raceSchedule.length > 0 && (
            <Badge variant="secondary" className="ml-1 text-xs px-2">
              {raceSchedule.length}
            </Badge>
          )}
        </Button>
      </DialogTrigger>
      <DialogContent className="h-[85vh] sm:max-w-5xl p-0 gap-0 flex flex-col overflow-hidden">
        <DialogHeader className="px-6 py-4 border-b bg-muted/30">
          <DialogTitle className="flex items-center gap-2 text-xl">
            <CalendarDays className="w-5 h-5 text-primary" />
            Race Schedule
            <span className="text-xs font-normal text-muted-foreground">from {data.source}</span>
          </DialogTitle>
        </DialogHeader>

        {/* FILTERS */}
        <div className="px-6 py-3 border-b flex flex-wrap items-center gap-x-5 gap-y-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Race or racetrack..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 w-52 pl-8 shadow-none"
            />
          </div>
          <ChipGroup label="Year" options={YEARS} selected={years} setSelected={setYears} format={(y) => y.replace(" Year", "")} />
          <ChipGroup label="Grade" options={GRADES} selected={grades} setSelected={setGrades} />
          <ChipGroup label="Distance" options={DISTANCES} selected={distances} setSelected={setDistances} />
          <ChipGroup label="Surface" options={TERRAINS} selected={terrains} setSelected={setTerrains} />
          {unpickable > 0 && (
            <Chip active={pickableOnly} onClick={() => setPickableOnly(!pickableOnly)}>
              Pickable only
            </Chip>
          )}
          {filtering && (
            <button type="button" onClick={resetFilters} className="text-sm text-muted-foreground hover:text-primary flex items-center gap-1">
              <X className="w-3.5 h-3.5" /> Reset ({visibleCount} shown)
            </button>
          )}
        </div>

        <div className="flex-1 min-h-0 grid grid-rows-[1fr_auto] md:grid-rows-1 md:grid-cols-[1fr_18rem]">
          {/* RACES */}
          <div className="min-h-0 overflow-y-auto px-6 pb-6">
            {visible.length === 0 && (
              <p className="text-sm text-muted-foreground text-center mt-10">
                No race matches these filters.
              </p>
            )}
            {visible.map(({ year, races }) => (
              <section key={year}>
                <h3 className="sticky top-0 z-10 bg-background pt-4 pb-2 text-lg font-semibold">
                  {year}
                </h3>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
                  {races.map(([name, detail]) => {
                    const selected = isScheduled(name, year);
                    const canPick = pickable(detail);
                    return (
                      <button
                        key={name}
                        type="button"
                        // Still clickable when scheduled, so an old entry can be removed.
                        disabled={!canPick && !selected}
                        title={canPick ? undefined : `No assets/races/${name}.png, so the bot can't pick this race.`}
                        onClick={() => toggle(name, year, detail.date)}
                        className={`text-left rounded-md border-2 px-3 py-2 transition disabled:cursor-not-allowed disabled:opacity-50 ${
                          selected
                            ? "border-primary bg-primary/10"
                            : "border-border enabled:hover:border-primary/50"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <p className="font-semibold leading-tight">
                            {selected && <Check className="inline w-4 h-4 mr-1 text-primary" />}
                            {name}
                            {detail.grade && (
                              <span className="ml-1.5 align-middle text-[10px] font-semibold rounded px-1 py-0.5 border border-primary/40 text-primary">
                                {detail.grade}
                              </span>
                            )}
                          </p>
                          <span className="shrink-0 text-sm text-muted-foreground">{detail.date}</span>
                        </div>
                        <p className="text-sm mt-1">
                          {detail.distance.type} {detail.distance.meters}m · {detail.terrain} · {detail.racetrack}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                          {detail.sparks.length > 0 && <>Sparks: {detail.sparks.join(", ")} · </>}
                          Fans {detail.fans.required.toLocaleString()} req / +{detail.fans.gained.toLocaleString()}
                        </p>
                        {!canPick && (
                          <p className="text-xs text-destructive mt-1">No race image, so the bot can't pick it</p>
                        )}
                      </button>
                    );
                  })}
                </div>
              </section>
            ))}
          </div>

          {/* SCHEDULED */}
          <div className="min-h-0 max-h-[30vh] md:max-h-none flex flex-col border-t md:border-t-0 md:border-l bg-muted/20">
            <div className="flex items-center justify-between px-4 py-3 border-b">
              <p className="font-semibold">Scheduled ({raceSchedule.length})</p>
              <Button size="sm" variant="outline" disabled={raceSchedule.length === 0} onClick={clearRaceSchedule}>
                Clear
              </Button>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto p-3 flex flex-col gap-2">
              {scheduled.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center mt-6">
                  Click a race to schedule it.
                </p>
              ) : (
                scheduled.map((race) => (
                  <div
                    key={`${race.year}-${race.name}`}
                    className="flex items-center gap-2 rounded-md border bg-background px-3 py-2"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate">{race.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {race.year} · {race.date}
                      </p>
                    </div>
                    <button
                      type="button"
                      aria-label={`Remove ${race.name}`}
                      onClick={() => deleteRaceSchedule(race.name, race.year)}
                      className="p-1 text-muted-foreground hover:text-destructive"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
