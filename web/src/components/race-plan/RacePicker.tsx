import { useState } from "react";
import { Search, Check, Ban, Sparkles } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../ui/dialog";
import { Input } from "../ui/input";
import { URL } from "@/constants";
import type { PlannedRace, Turn } from "./RacePlanView";

// Picking the race for one turn.
//
// This replaced a plain <select>, which showed a truncated name and nothing
// else - no grade, no surface, no distance, so choosing meant knowing the
// calendar by heart.
//
// **On pictures.** Only 30 of the planner's 402 races have one: the
// template-matching crops in assets/races/, which exist because `race_select`
// needs them to click a race, not because anyone drew them for a UI. The
// game's own thumbnails are inside its encrypted asset bundles, and GameTora -
// where server/images.py gets character and support art - has no race art
// (checked 2026-09-21). So a race without a crop gets a tile drawn from its own
// surface and grade instead of a broken image. That is also why the crop is
// shown small and letterboxed: it is a ~140x70 grab of a game widget, and
// blowing it up only makes it look wrong.

const TURF = "from-emerald-900/50 to-emerald-700/30 text-emerald-200";
const DIRT = "from-amber-900/50 to-amber-700/30 text-amber-200";

type Props = {
  turn: Turn;
  value: string;
  auto: string;
  none: string;
  onPick: (value: string) => void;
  onClose: () => void;
};

function Thumb({ race }: { race: PlannedRace }) {
  const tone = race.terrain === "Dirt" ? DIRT : TURF;
  if (race.has_image) {
    return (
      <div className="flex h-14 w-full items-center justify-center overflow-hidden rounded-md border border-border/60 bg-background">
        <img
          src={`${URL}/data/race_image/${encodeURIComponent(race.name)}`}
          alt=""
          loading="lazy"
          className="max-h-full max-w-full object-contain"
        />
      </div>
    );
  }
  return (
    <div
      className={`flex h-14 w-full flex-col items-center justify-center rounded-md border border-border/60 bg-gradient-to-br ${tone}`}
      aria-hidden
    >
      <span className="text-sm font-semibold leading-none">{race.grade ?? "—"}</span>
      <span className="mt-1 text-[10px] uppercase tracking-wide opacity-80">
        {race.terrain ?? ""}
      </span>
    </div>
  );
}

export default function RacePicker({ turn, value, auto, none, onPick, onClose }: Props) {
  const [search, setSearch] = useState("");
  const query = search.trim().toLowerCase();

  const options = turn.options.filter(
    (o) =>
      !query ||
      o.name.toLowerCase().includes(query) ||
      (o.racetrack ?? "").toLowerCase().includes(query) ||
      (o.grade ?? "").toLowerCase().includes(query)
  );

  const card = (selected: boolean) =>
    `flex flex-col gap-2 rounded-lg border-2 p-2.5 text-left transition ${
      selected ? "border-primary bg-primary/10" : "border-border hover:border-primary/50"
    }`;

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="flex h-[85vh] flex-col gap-0 overflow-hidden p-0 sm:max-w-3xl">
        <DialogHeader className="border-b bg-muted/30 px-6 py-4">
          <DialogTitle className="text-xl">
            {turn.year} · {turn.date}
          </DialogTitle>
          <DialogDescription>
            {turn.options.length} race{turn.options.length === 1 ? "" : "s"} run on this turn.
            {turn.pinned && " An epithet depends on this turn."}
          </DialogDescription>
        </DialogHeader>

        <div className="border-b px-6 py-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              autoFocus
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Race, racetrack or grade..."
              className="h-9 pl-8"
            />
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <button type="button" onClick={() => onPick(auto)} className={card(value === auto)}>
              <div className="flex h-14 w-full items-center justify-center rounded-md border border-dashed border-border/60">
                <Sparkles className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-sm font-semibold leading-tight">
                  {value === auto && <Check className="mr-1 inline h-3.5 w-3.5 text-primary" />}
                  Auto
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {turn.picked ? `Now: ${turn.picked}` : "Leaves the turn empty"}
                </p>
              </div>
            </button>

            <button type="button" onClick={() => onPick(none)} className={card(value === none)}>
              <div className="flex h-14 w-full items-center justify-center rounded-md border border-dashed border-border/60">
                <Ban className="h-5 w-5 text-muted-foreground" />
              </div>
              <div>
                <p className="text-sm font-semibold leading-tight">
                  {value === none && <Check className="mr-1 inline h-3.5 w-3.5 text-primary" />}
                  No race
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">Keep this turn free</p>
              </div>
            </button>

            {options.map((o) => (
              <button
                key={o.name}
                type="button"
                onClick={() => onPick(o.name)}
                className={card(value === o.name)}
              >
                <Thumb race={o} />
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold leading-tight" title={o.name}>
                    {value === o.name && <Check className="mr-1 inline h-3.5 w-3.5 text-primary" />}
                    {o.name}
                  </p>
                  <p className="mt-1 flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
                    <span className="rounded border border-primary/40 px-1 py-0.5 text-[10px] font-semibold text-primary">
                      {o.grade ?? "—"}
                    </span>
                    <span>{o.racetrack}</span>
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {[o.terrain, o.distance ? `${o.distance.type} ${o.distance.meters}m` : null]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                  <p className="mt-1 text-xs tabular-nums text-muted-foreground">
                    +{o.stats} stats · {o.sp} SP
                    {!o.has_image && (
                      <span
                        className="ml-1 rounded border border-border px-1 py-0.5 text-[10px] uppercase"
                        title="No picture asset, so the bot cannot click this race. Fine to enter in the game's Agenda by hand."
                      >
                        agenda
                      </span>
                    )}
                  </p>
                </div>
              </button>
            ))}
          </div>

          {options.length === 0 && (
            <p className="mt-10 text-center text-sm text-muted-foreground">
              {turn.options.length === 0
                ? "No race runs on this turn."
                : "No race matches that search."}
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
