import { useCallback, useEffect, useState } from "react";
import { Repeat, RotateCcw } from "lucide-react";
import { Button } from "../ui/button";
import { Checkbox } from "../ui/checkbox";
import { Input } from "../ui/input";
import { URL } from "@/constants";
import type { Config, UpdateConfigType } from "@/types";

type Props = {
  config: Config;
  updateConfig: UpdateConfigType;
};

const FALLBACK = { enabled: false, borrow_card: "", max_consecutive: 0 };

// What happens once a career finishes: whether the bot starts the next one by
// itself, which card it re-borrows, and how many it may run before stopping.
// Its own card rather than a corner of Skills - these settings are about the
// run, not about the career being played.
export default function CareerStartSection({ config, updateConfig }: Props) {
  // Presets saved before this existed don't carry it.
  const careerStart = { ...FALLBACK, ...(config.career_start ?? {}) };
  const restartOnFreeze = config.restart_on_freeze ?? false;
  const set = (patch: Partial<typeof FALLBACK>) =>
    updateConfig("career_start", { ...careerStart, ...patch });

  // The count is the bot's, not the config's: it lives in the career ledger so
  // it survives the restart that follows a frozen client. Read it, don't guess.
  const [started, setStarted] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${URL}/career/count`, { cache: "no-store" });
      if (res.ok) setStarted((await res.json()).started ?? null);
    } catch {
      setStarted(null);
    }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  const reset = async () => {
    setBusy(true);
    try {
      const res = await fetch(`${URL}/career/reset`, { method: "POST" });
      if (res.ok) setStarted(0);
    } catch {
      // Leave the count as it was; the next refresh corrects it.
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-card p-6 rounded-xl shadow-lg border border-border/20">
      <h2 className="text-3xl font-semibold mb-6 flex items-center gap-3">
        <Repeat className="text-primary" />
        Next career
      </h2>
      <div className="flex flex-col gap-6">
        <div className="w-fit">
          {/* No shrink-0 on the label: it makes the text unwrappable, so w-fit
              resolves to the full line width and the row overflows the card. */}
          <label htmlFor="career-start" className="flex gap-2 items-start">
            <Checkbox id="career-start" className="mt-1.5" checked={careerStart.enabled}
              onCheckedChange={() => set({ enabled: !careerStart.enabled })} />
            <span className="text-lg font-medium">Start the next career by itself?</span>
          </label>
          <span className="text-sm text-muted-foreground">
            At the home screen after a career, walks Scenario &rarr; Trainee &rarr; Legacy &rarr; Support Formation
            keeping everything the last career used, re-borrows the Friends card and presses Start Career!.
            Costs 30 TP. Off, the bot stops at the home screen as it always has.
          </span>
        </div>
        <div className="w-fit">
          <label htmlFor="borrow-card" className="block text-lg font-medium">
            Card to borrow
          </label>
          <Input id="borrow-card" className="w-64 mt-1" value={careerStart.borrow_card}
            placeholder="Light Hello"
            onChange={(e) => set({ borrow_card: e.target.value })} />
          <span className="block text-sm text-muted-foreground mt-1">
            The Friends slot is the one thing a new career forgets, and a deck without it will not start. After the
            first career the bot reuses whatever it borrowed last time; this is only the seed for the first one.
          </span>
        </div>
        <div className="w-fit">
          <label htmlFor="max-consecutive" className="block text-lg font-medium">
            Careers per run
          </label>
          <Input id="max-consecutive" className="w-24 mt-1" type="number" min={0}
            value={careerStart.max_consecutive}
            onChange={(e) =>
              set({ max_consecutive: Number.isNaN(e.target.valueAsNumber) ? 0 : e.target.valueAsNumber })} />
          <span className="block text-sm text-muted-foreground mt-1">
            Stop after starting this many careers. <strong>0</strong> is no limit. A career already in progress when you
            start the bot is not counted &mdash; it was not one of these.
          </span>
        </div>
        <div>
          <div className="text-lg font-medium">
            Careers started: {started == null ? "\u2014" : started}
            {careerStart.max_consecutive ? ` / ${careerStart.max_consecutive}` : ""}
          </div>
          <div className="flex items-center gap-3 mt-2">
            <Button variant="outline" onClick={reset} disabled={busy || started === 0}>
              <RotateCcw className="size-4" />
              Reset count
            </Button>
            <Button variant="ghost" onClick={() => void refresh()} disabled={busy}>
              Refresh
            </Button>
          </div>
          <span className="block text-sm text-muted-foreground mt-2">
            Counted in <code>logs/career_start_progress.json</code>, one row per career with its own id, so the count
            survives restarting the bot &mdash; which is what happens every time the game client freezes. Reset it to
            start a fresh run. This is the bot's own count, not a setting: Reset takes effect at once, with no Apply.
          </span>
        </div>
      </div>
      <div className="h-px bg-border/60 my-6" />
      <div className="flex flex-col gap-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Recovery</p>
        <div className="w-fit">
          <label htmlFor="restart-on-freeze" className="flex gap-2 items-start">
            <Checkbox id="restart-on-freeze" className="mt-1.5" checked={restartOnFreeze}
              onCheckedChange={() => updateConfig("restart_on_freeze", !restartOnFreeze)} />
            <span className="text-lg font-medium">Restart the game if it freezes?</span>
          </label>
          <span className="text-sm text-muted-foreground">
            The client stops drawing every few hours &mdash; it keeps a full frame on screen and never changes it. The
            bot spots that after 10 identical frames (~90s), and with this on it closes the game, launches it again,
            taps past the title screen and resumes the career through Continue Career. Off, it stops and waits for you.
            It ends the game process, so leave it off if you ever watch over its shoulder.
          </span>
        </div>
      </div>
    </div>
  );
}
