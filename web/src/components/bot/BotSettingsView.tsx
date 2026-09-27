import { useCallback, useEffect, useRef, useState } from "react";
import { Cog, RotateCcw } from "lucide-react";
import { Button } from "../ui/button";
import { Checkbox } from "../ui/checkbox";
import { Input } from "../ui/input";
import { URL } from "@/constants";

type CareerStart = { enabled: boolean; borrow_card: string; max_consecutive: number };
type Settings = {
  sleep_time_multiplier: number;
  tp_bottle_floor: number;
  reroll_sparks: boolean;
  restart_on_freeze: boolean;
  career_start: CareerStart;
};

const EMPTY: Settings = {
  sleep_time_multiplier: 1,
  tp_bottle_floor: 50,
  reroll_sparks: true,
  restart_on_freeze: false,
  career_start: { enabled: false, borrow_card: "", max_consecutive: 0 },
};
const CARD = "bg-card p-6 rounded-xl shadow-lg border border-border/20";
// Same as the Configuration tab's, and for the same reason: long enough that
// typing a number doesn't write the file per keystroke, short enough that
// nobody leaves the page before their last edit lands.
const DEBOUNCE = 500;

type SaveState = "idle" | "error";

// bot.json holds keys this page does not show, and save_bot() merges rather
// than replaces, so what comes back is not what went out. Shaping both the read
// and the echo through here is what lets "has the page changed?" be a string
// comparison.
const shape = (body: Partial<Settings>): Settings => ({
  ...EMPTY,
  ...body,
  career_start: { ...EMPTY.career_start, ...body.career_start },
});

// How the bot *runs*, as against what it trains.
//
// These live in bot.json and this tab reads and writes that file directly, the
// same arrangement as the Telegram tab and for the same reason: config presets
// under uma_configs/ describe a trainee and are meant to be swapped, while
// these describe this machine and this run. Loading a different preset should
// not change whether a frozen game gets restarted.
//
// **Every change is written, debounced - there is no Save button** (2026-09-27),
// which is what the Configuration tab already does. A settings page with a Save
// button looks identical whether or not it was pressed, and here the cost of
// missing it is silent: the bot goes on running the old value and says nothing.
//
// Two rules make auto-saving safe, both learned on the Configuration tab:
//
// - **nothing is written before the first GET answers.** This page starts from
//   EMPTY, and posting that would reset a settled machine to defaults. The
//   baseline stays null until the server has been read, and a read that fails
//   leaves it null, so a page that could not load never writes.
// - **a save in flight never overwrites what is being typed.** The echo is
//   adopted only when the page has not moved on since the request went out.
export default function BotSettingsView() {
  const [settings, setSettings] = useState<Settings>(EMPTY);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [error, setError] = useState<string | null>(null);
  // What bot.json holds, in this page's shape. null until the first read has
  // answered, and nothing is ever written while it is null.
  const onDisk = useRef<string | null>(null);
  // The career count is the bot's own running total, not a setting; it lives in
  // the career ledger so it survives the restart a frozen client forces.
  const [started, setStarted] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([
        fetch(`${URL}/bot-settings`, { cache: "no-store" }),
        fetch(`${URL}/career/count`, { cache: "no-store" }),
      ]);
      if (!s.ok) throw new Error(`HTTP ${s.status}`);
      const body = shape(await s.json());
      onDisk.current = JSON.stringify(body);
      setSettings(body);
      if (c.ok) setStarted((await c.json()).started ?? null);
      setError(null);
    } catch (e) {
      setError(
        `${e instanceof Error ? e.message : "could not reach the server"} - nothing on this page is being saved.`
      );
      setSaveState("error");
    } finally {
      setLoaded(true);
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const set = (patch: Partial<Settings>) => setSettings((s) => ({ ...s, ...patch }));
  const setCareer = (patch: Partial<CareerStart>) =>
    set({ career_start: { ...settings.career_start, ...patch } });

  const save = useCallback(async (next: Settings) => {
    const sent = JSON.stringify(next);
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${URL}/bot-settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: sent,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const echoed = shape(await res.json());
      onDisk.current = JSON.stringify(echoed);
      // Only take the server's copy when nothing has been typed since the
      // request went out; otherwise the newer edit stands and the effect below
      // saves it next.
      setSettings((cur) => (JSON.stringify(cur) === sent ? echoed : cur));
      setSaveState("idle");
    } catch (e) {
      setError(e instanceof Error ? e.message : "could not save");
      setSaveState("error");
    } finally {
      setBusy(false);
    }
  }, []);

  // Write every change, debounced. The state is cleared as soon as the page
  // differs from the file, so a stale "Not saved" never sits over an edit that
  // is about to be written.
  useEffect(() => {
    if (onDisk.current === null) return;
    if (JSON.stringify(settings) === onDisk.current) return;
    setSaveState("idle");
    const timer = setTimeout(() => void save(settings), DEBOUNCE);
    return () => clearTimeout(timer);
  }, [settings, save]);

  const resetCount = async () => {
    setBusy(true);
    try {
      const res = await fetch(`${URL}/career/reset`, { method: "POST" });
      if (res.ok) setStarted(0);
    } catch {
      // The next load corrects it.
    } finally {
      setBusy(false);
    }
  };

  const num = (e: React.ChangeEvent<HTMLInputElement>, fallback: number) =>
    Number.isNaN(e.target.valueAsNumber) ? fallback : e.target.valueAsNumber;

  if (!loaded) return <p className="text-muted-foreground mx-2">Loading...</p>;

  return (
    <div className="flex flex-col gap-6 mx-2">
      <div className={CARD}>
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <h2 className="text-3xl font-semibold flex items-center gap-3">
            <Cog className="text-primary" />
            Bot
          </h2>
          {/* No Save button: every change is written. Silent while it works and
              when it lands, loud only when a write fails - at which point the
              page and the bot disagree, which is the state a Save button used
              to hide. */}
          <div className="flex items-center gap-3">
            {saveState === "error" && (
              <>
                <span className="text-red-600 dark:text-red-400">Not saved: {error}</span>
                {onDisk.current !== null && (
                  <Button variant="outline" onClick={() => void save(settings)} disabled={busy}>
                    <RotateCcw className="size-4" />
                    Retry
                  </Button>
                )}
              </>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-6">
          <div>
            <label htmlFor="sleep-multiplier" className="block text-lg font-medium">
              Sleep time multiplier
            </label>
            <Input id="sleep-multiplier" className="w-24 mt-1" type="number" min={0.1} step={0.1}
              value={settings.sleep_time_multiplier}
              onChange={(e) => set({ sleep_time_multiplier: num(e, 1) })} />
            <span className="block text-sm text-muted-foreground mt-1">
              Every wait the bot makes is multiplied by this. Raise it on a slower machine, where a screen that has not
              finished drawing gets read as the wrong screen.
            </span>
          </div>

          <div>
            <label htmlFor="tp-floor" className="block text-lg font-medium">
              Keep at least this many TP bottles
            </label>
            <Input id="tp-floor" className="w-24 mt-1" type="number" min={0}
              value={settings.tp_bottle_floor}
              onChange={(e) => set({ tp_bottle_floor: num(e, 50) })} />
            <span className="block text-sm text-muted-foreground mt-1">
              The bot spends a bottle to reroll sparks, or to afford a career it is short of TP for &mdash; but never
              below this. Only the plain <em>Toughness 30</em> bottle is ever spent; Carats and the handmade chocolates
              are left alone.
            </span>
          </div>
        </div>
      </div>

      <div className={CARD}>
        <h3 className="text-xl font-semibold mb-4">Career end</h3>
        <div className="w-fit">
          <label htmlFor="reroll-sparks" className="flex gap-2 items-start">
            <Checkbox id="reroll-sparks" className="mt-1.5" checked={settings.reroll_sparks}
              onCheckedChange={() => set({ reroll_sparks: !settings.reroll_sparks })} />
            <span className="text-lg font-medium">Reroll sparks without a 3&#9733; blue?</span>
          </label>
          <span className="text-sm text-muted-foreground">
            Costs 30 TP at career end, and the original set stays on offer &mdash; the bot keeps whichever ranks
            higher. A bottle may be spent to afford it, subject to the floor above.
          </span>
        </div>
      </div>

      <div className={CARD}>
        <h3 className="text-xl font-semibold mb-4">Next career</h3>
        <div className="flex flex-col gap-6">
          <div className="w-fit">
            <label htmlFor="career-start" className="flex gap-2 items-start">
              <Checkbox id="career-start" className="mt-1.5" checked={settings.career_start.enabled}
                onCheckedChange={() => setCareer({ enabled: !settings.career_start.enabled })} />
              <span className="text-lg font-medium">Start the next career by itself?</span>
            </label>
            <span className="text-sm text-muted-foreground">
              At the home screen after a career, walks Scenario &rarr; Trainee &rarr; Legacy &rarr; Support Formation
              keeping everything the last career used, re-borrows the Friends card and presses Start Career!.
              Costs 30 TP. Off, the bot stops at the home screen.
            </span>
          </div>

          <div>
            <label htmlFor="borrow-card" className="block text-lg font-medium">Card to borrow</label>
            <Input id="borrow-card" className="w-64 mt-1" placeholder="Light Hello"
              value={settings.career_start.borrow_card}
              onChange={(e) => setCareer({ borrow_card: e.target.value })} />
            <span className="block text-sm text-muted-foreground mt-1">
              The Friends slot is the one thing a new career forgets, and a deck without it will not start. After the
              first career the bot reuses whatever it borrowed last time; this is only the seed for the first one.
            </span>
          </div>

          <div>
            <label htmlFor="max-consecutive" className="block text-lg font-medium">Careers per run</label>
            <Input id="max-consecutive" className="w-24 mt-1" type="number" min={0}
              value={settings.career_start.max_consecutive}
              onChange={(e) => setCareer({ max_consecutive: num(e, 0) })} />
            <span className="block text-sm text-muted-foreground mt-1">
              Stop after starting this many careers. <strong>0</strong> is no limit. A career already in progress when
              you start the bot is not counted &mdash; it was not one of these.
            </span>
          </div>

          <div>
            <div className="text-lg font-medium">
              Careers started: {started == null ? "—" : started}
              {settings.career_start.max_consecutive ? ` / ${settings.career_start.max_consecutive}` : ""}
            </div>
            <Button variant="outline" className="mt-2" onClick={resetCount}
              disabled={busy || started === 0}>
              <RotateCcw className="size-4" />
              Reset count
            </Button>
            <span className="block text-sm text-muted-foreground mt-2">
              One row per career, each with its own id, so the count survives restarting the bot &mdash; which is what
              happens every time the game client freezes.
            </span>
          </div>
        </div>
      </div>

      <div className={CARD}>
        <h3 className="text-xl font-semibold mb-4">Recovery</h3>
        <div className="w-fit">
          <label htmlFor="restart-on-freeze" className="flex gap-2 items-start">
            <Checkbox id="restart-on-freeze" className="mt-1.5" checked={settings.restart_on_freeze}
              onCheckedChange={() => set({ restart_on_freeze: !settings.restart_on_freeze })} />
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
