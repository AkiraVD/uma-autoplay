import { useEffect, useState } from "react";
import { FolderOpen, Loader2, AlertTriangle } from "lucide-react";
import { Button } from "../ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog";
import { URL } from "@/constants";
import type { RaceScheduleType } from "@/types";

// Loads a race list saved by the Race Plan tab into config.race_schedule.
//
// Only the runnable races come across. The planner deliberately admits OP races
// so a plan can be typed into the game's own Agenda by hand, but `race_select`
// finds a race by assets/races/<name>.png - handing the bot one without a
// picture would let the goal-race path burn the turn silently. The count of
// what was left behind is shown rather than hidden.

type SavedList = {
  name: string;
  title: string;
  races: number;
  runnable: number;
  epithets: number;
  saved_at: number;
  unreadable: boolean;
};

type SavedRace = {
  name: string;
  year: string;
  date: string;
  has_image?: boolean;
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

type Props = {
  onLoad: (rows: RaceScheduleType[]) => void;
};

export default function LoadRaceList({ onLoad }: Props) {
  const [open, setOpen] = useState(false);
  const [lists, setLists] = useState<SavedList[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    fetch(`${URL}/race_lists`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setLists)
      .catch(() => setError("couldn't reach the server for the saved lists"));
  }, [open]);

  const load = async (name: string) => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${URL}/race_lists/${encodeURIComponent(name)}`);
      if (!res.ok) throw new Error((await res.json()).detail ?? `server said ${res.status}`);
      const data = await res.json();
      const rows: RaceScheduleType[] = (data.races ?? [])
        .filter((r: SavedRace) => r.has_image !== false)
        .map((r: SavedRace) => ({ name: r.name, year: r.year, date: r.date }));
      onLoad(rows);
      setLoaded(`Loaded ${rows.length} races from "${data.title || name}"`);
      setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild>
          <Button variant="outline" className="w-fit flex items-center gap-2">
            <FolderOpen className="w-4 h-4" />
            Load saved list
          </Button>
        </DialogTrigger>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>Saved race lists</DialogTitle>
            <DialogDescription>
              Built in the Race Plan tab and kept in <code>uma_race_lists/</code>. Loading one
              replaces the schedule above.
            </DialogDescription>
          </DialogHeader>

          {error && (
            <p className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <AlertTriangle className="h-4 w-4" /> {error}
            </p>
          )}

          <div className="max-h-[45vh] overflow-y-auto rounded-lg border border-border">
            {lists.length === 0 ? (
              <p className="px-3 py-8 text-center text-sm text-muted-foreground">
                Nothing saved yet — build a plan in the Race Plan tab first.
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {lists.map((s) => (
                  <li key={s.name} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2">
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
                        {s.runnable} of {s.races} runnable · {s.epithets} epithets
                        <span className="ml-2 opacity-70">{when(s.saved_at)}</span>
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busy || s.unreadable || s.runnable === 0}
                      title={s.runnable === 0 ? "No race in this list has a picture the bot can click." : undefined}
                      onClick={() => load(s.name)}
                    >
                      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Load"}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </DialogContent>
      </Dialog>
      {loaded && <p className="text-sm text-muted-foreground">{loaded}</p>}
    </div>
  );
}
