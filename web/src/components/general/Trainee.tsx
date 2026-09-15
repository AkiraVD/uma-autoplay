import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import Tooltips from "@/components/_c/Tooltips";
import { Search, User, X } from "lucide-react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { URL } from "@/constants";

// Mirrors core/trainee.py: GRADE, STYLE and the column order of the profile it
// returns. Nothing here is a fallback list - without master.mdb the bot can't
// read her numbers either, so the picker is simply empty.
const GRADE: Record<number, string> = {
  1: "G", 2: "F", 3: "E", 4: "D", 5: "C", 6: "B", 7: "A", 8: "S",
};
const DISTANCES = ["sprint", "mile", "medium", "long"];
const STYLES = ["front", "pace", "late", "end"];
// Below B an aptitude is a real handicap; core/trainee.py warns on the same line.
const USABLE = 6;

type TraineeType = {
  id: number;
  chara_id: number;
  name: string;
  rarity: number;
  style: string;
  growth: Record<string, number>;
  aptitude: Record<string, number>;
  // Server-side path, cached by server/images.py. A handful of story cards
  // have no picture on GameTora, so this 404s and Portrait falls back.
  art?: string;
};

type TraineeData = {
  source: string;
  trainees: TraineeType[];
};

const EMPTY: TraineeData = { source: "", trainees: [] };

// Throws on failure so the query retries: a server older than /data/trainees
// answers with the page, which isn't JSON.
const getTraineeData = async (): Promise<TraineeData> => {
  const res = await fetch(`${URL}/data/trainees`);
  if (!res.ok) throw new Error(`TRAINEES-FETCH: HTTP ${res.status}`);
  return await res.json();
};

// The art is a standing pose, so it's anchored to the top of the box: centring
// it crops the face out, which is the only part that identifies her at 48px.
function Portrait({ trainee, size }: { trainee?: TraineeType; size: number }) {
  const [broken, setBroken] = useState(false);
  const box = {
    width: size,
    height: size,
    minWidth: size,
  };

  if (!trainee?.art || broken) {
    return (
      <div
        style={box}
        className="rounded-md bg-muted flex items-center justify-center shrink-0"
      >
        <User className="w-1/2 h-1/2 text-muted-foreground" />
      </div>
    );
  }
  return (
    <img
      src={`${URL}${trainee.art}`}
      alt=""
      loading="lazy"
      style={box}
      onError={() => setBroken(true)}
      className="rounded-md object-cover object-top bg-muted shrink-0"
    />
  );
}

function Apt({ label, value }: { label: string; value: number }) {
  const grade = GRADE[value] ?? "?";
  return (
    <span
      className={`text-xs px-1.5 py-0.5 rounded border ${
        value >= USABLE
          ? "border-primary/60 text-primary"
          : "border-border/50 text-muted-foreground"
      }`}
    >
      {label} {grade}
    </span>
  );
}

type Props = {
  trainee: string;
  setTrainee: (newVal: string) => void;
};

export default function Trainee({ trainee, setTrainee }: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const { data = EMPTY, isLoading } = useQuery<TraineeData>({
    queryKey: ["trainees"],
    queryFn: getTraineeData,
  });

  const query = search.trim().toLowerCase();
  const visible = data.trainees.filter(
    (t) => query === "" || t.name.toLowerCase().includes(query)
  );

  const selected = data.trainees.find((t) => t.name === trainee);

  const pick = (name: string) => {
    setTrainee(name);
    setOpen(false);
  };

  return (
    // min-w-0 all the way down: a grid item defaults to min-width:auto, so
    // without it a long "[Title] Name" pushes the button out over the next
    // column instead of the span truncating.
    // "[Gilded Shrine to Glory] Kitasan Black" is the normal length here, not
    // the worst case, so it gets a whole row of its section.
    <label className="flex flex-col gap-2 min-w-0">
      <div className="flex gap-2 items-center">
        <span className="text-lg font-medium">Trainee</span>
        <Tooltips>
          Who this career is training. The bot reads her aptitudes and growth
          from master.mdb and warns when the config disagrees. Advisory only.
        </Tooltips>
      </div>

      <div className="flex items-center gap-2 min-w-0">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button
              variant={trainee ? "secondary" : "default"}
              // `shrink` overrides the shrink-0 in buttonVariants' base classes
              // - without it the trigger can't give way, so a long name pushes
              // the clear X out over the next column instead of truncating.
              className="min-w-0 shrink justify-start flex items-center gap-2 h-auto py-1.5"
            >
              {trainee ? (
                /* Keyed so picking a different trainee clears a stale "broken". */
                <Portrait key={selected?.id} trainee={selected} size={28} />
              ) : (
                <User className="w-4 h-4 shrink-0" />
              )}
              <span className="truncate min-w-0">
                {trainee || "Select Trainee"}
              </span>
            </Button>
          </DialogTrigger>
          <DialogContent className="h-[85vh] sm:max-w-3xl p-0 gap-0 flex flex-col overflow-hidden">
            <DialogHeader className="px-6 py-4 border-b bg-muted/30">
              <DialogTitle className="flex items-center gap-2 text-xl">
                <User className="w-5 h-5 text-primary" />
                Trainee
                <span className="text-xs font-normal text-muted-foreground">
                  {data.source ? `from ${data.source}` : ""}
                </span>
              </DialogTitle>
            </DialogHeader>

            <div className="px-6 py-3 border-b">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  type="search"
                  placeholder="Name or title..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-8 w-full max-w-sm"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-3 flex flex-col gap-1.5">
              {isLoading && (
                <p className="text-sm text-muted-foreground">Reading master.mdb...</p>
              )}
              {!isLoading && data.trainees.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No trainee list. The game's master.mdb wasn't readable, so
                  there's nothing to pick from &mdash; type the name into
                  config.json if you know it.
                </p>
              )}
              {visible.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => pick(t.name)}
                  className={`text-left px-3 py-2 rounded-lg border transition-colors flex gap-3 items-start ${
                    t.name === trainee
                      ? "border-primary bg-primary/10"
                      : "border-border/50 hover:border-primary"
                  }`}
                >
                  <Portrait trainee={t} size={56} />
                  <div className="min-w-0">
                    <div className="font-medium">{t.name}</div>
                    <div className="flex flex-wrap items-center gap-1 mt-1">
                      {DISTANCES.map((d) => (
                        <Apt key={d} label={d} value={t.aptitude[d]} />
                      ))}
                      <span className="w-2" />
                      {STYLES.map((s) => (
                        <Apt key={s} label={s} value={t.aptitude[s]} />
                      ))}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      turf {GRADE[t.aptitude.turf] ?? "?"} / dirt{" "}
                      {GRADE[t.aptitude.dirt] ?? "?"}
                      {" · growth "}
                      {Object.entries(t.growth)
                        .map(([k, v]) => `${k} +${v}%`)
                        .join(", ") || "none"}
                      {` · style ${t.style}`}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </DialogContent>
        </Dialog>

        {trainee && (
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0"
            title="Clear"
            onClick={() => setTrainee("")}
          >
            <X className="w-4 h-4" />
          </Button>
        )}
      </div>
    </label>
  );
}
