import { useCallback, useEffect, useRef, useState } from "react";
import { Send, MessageCircle, RotateCcw } from "lucide-react";
import { Button } from "../ui/button";
import { Checkbox } from "../ui/checkbox";
import { Input } from "../ui/input";
import { URL } from "@/constants";

type Settings = { enabled: boolean; token: string; chat_id: string };

const EMPTY: Settings = { enabled: false, token: "", chat_id: "" };
const CARD = "bg-card p-6 rounded-xl shadow-lg border border-border/20";
// Same as the Bot and Configuration tabs', and for the same reason: long enough
// that typing a token doesn't write the file per keystroke, short enough that
// nobody leaves the page before their last edit lands.
const DEBOUNCE = 500;

// Telegram, for following a run nobody is watching.
//
// These settings are *not* part of the config. They live in telegram.json and
// this tab reads and writes that file on its own, for two reasons: the token is
// a secret and config presets under uma_configs/ are meant to be saved, swapped
// and shared, and these belong to the machine rather than to a trainee - so
// loading a different preset should not change who gets messaged.
//
// What follows from that, none of which the page says because none of it is
// anything to do: the Apply button on the Configuration tab does not touch
// these, saving here applies to the running bot at once with no restart, and
// telegram.json is gitignored so the token stays on this machine.
//
// **Every change is written, debounced - there is no Save button** (2026-09-28),
// the same arrangement the Bot and Configuration tabs have. The page says
// nothing when a write succeeds: the only thing worth interrupting anyone for is
// a write that *failed*, because then the page and the bot disagree, which is
// the state a Save button used to hide.
//
// Two rules make auto-saving safe, both inherited from useConfig.ts:
//
// - **nothing is written before the first GET answers.** This page starts from
//   EMPTY, and posting that would wipe a settled token. The baseline stays null
//   until the server has been read, and a read that fails leaves it null, so a
//   page that could not load never writes.
// - **a save in flight never overwrites what is being typed.** The echo is
//   adopted only when the page has not moved on since the request went out.
export default function TelegramView() {
  const [settings, setSettings] = useState<Settings>(EMPTY);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // What telegram.json holds, in this page's shape. null until the first read
  // has answered, and nothing is ever written while it is null.
  const onDisk = useRef<string | null>(null);
  const [result, setResult] = useState<{ ok: boolean; reason?: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${URL}/telegram`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = { ...EMPTY, ...(await res.json()) };
      onDisk.current = JSON.stringify(body);
      setSettings(body);
      setError(null);
    } catch (e) {
      setError(
        `${e instanceof Error ? e.message : "could not reach the server"} - nothing on this page is being saved.`
      );
    } finally {
      setLoaded(true);
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const set = (patch: Partial<Settings>) => setSettings((s) => ({ ...s, ...patch }));

  const save = useCallback(async (next: Settings) => {
    const sent = JSON.stringify(next);
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${URL}/telegram`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: sent,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const echoed = { ...EMPTY, ...(await res.json()) };
      onDisk.current = JSON.stringify(echoed);
      // Only take the server's copy when nothing has been typed since the
      // request went out; otherwise the newer edit stands and the effect below
      // saves it next.
      setSettings((cur) => (JSON.stringify(cur) === sent ? echoed : cur));
    } catch (e) {
      setError(e instanceof Error ? e.message : "could not save");
    } finally {
      setBusy(false);
    }
  }, []);

  // Write every change, debounced.
  useEffect(() => {
    if (onDisk.current === null) return;
    if (JSON.stringify(settings) === onDisk.current) return;
    const timer = setTimeout(() => void save(settings), DEBOUNCE);
    return () => clearTimeout(timer);
  }, [settings, save]);

  // The test posts what is typed rather than what is saved, so it works before
  // saving - which is exactly when the details are most likely to be wrong.
  const test = async () => {
    setBusy(true);
    setResult(null);
    try {
      const res = await fetch(`${URL}/telegram/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: settings.token, chat_id: settings.chat_id }),
      });
      setResult(res.ok ? await res.json() : { ok: false, reason: `HTTP ${res.status}` });
    } catch (e) {
      setResult({ ok: false, reason: e instanceof Error ? e.message : "could not reach the server" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 mx-2">
      <div className={CARD}>
        <h2 className="text-3xl font-semibold mb-6 flex items-center gap-3">
          <MessageCircle className="text-primary" />
          Telegram
        </h2>
        {!loaded ? (
          <p className="text-muted-foreground">Loading...</p>
        ) : (
        <div className="flex flex-col gap-6">
          <div className="w-fit">
            <label htmlFor="telegram-enabled" className="flex gap-2 items-start">
              <Checkbox id="telegram-enabled" className="mt-1.5" checked={settings.enabled}
                onCheckedChange={() => set({ enabled: !settings.enabled })} />
              <span className="text-lg font-medium">Send me messages?</span>
            </label>
            <span className="text-sm text-muted-foreground">
              Off, nothing is sent and nothing is contacted.
            </span>
          </div>

          <div>
            <label htmlFor="telegram-token" className="block text-lg font-medium">
              Bot token
            </label>
            <Input id="telegram-token" type="password" autoComplete="off"
              className="w-full max-w-xl mt-1 font-mono"
              placeholder="123456789:AAE..."
              value={settings.token}
              onChange={(e) => set({ token: e.target.value })} />
            <span className="block text-sm text-muted-foreground mt-1">
              From <strong>@BotFather</strong> in Telegram: send it <code>/newbot</code>, pick a name, and it replies
              with the token.
            </span>
          </div>

          <div>
            <label htmlFor="telegram-chat" className="block text-lg font-medium">
              Chat ID
            </label>
            <Input id="telegram-chat" className="w-64 mt-1 font-mono"
              placeholder="123456789"
              value={settings.chat_id}
              onChange={(e) => set({ chat_id: e.target.value })} />
            <span className="block text-sm text-muted-foreground mt-1">
              Your own chat with the bot, not the bot's name. Message your new bot once, then open
              <code className="mx-1">api.telegram.org/bot&lt;token&gt;/getUpdates</code> in a browser and read
              <code className="mx-1">result[0].message.chat.id</code>. A group works too; its id starts with
              <code className="mx-1">-</code>.
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* No Save button: every change is written. Quiet while it works,
                loud only when a write fails. */}
            <Button variant="outline" onClick={test}
              disabled={busy || !settings.token || !settings.chat_id}>
              <Send className="size-4" />
              Send a test message
            </Button>
            {result && (
              <span className={result.ok ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}>
                {result.ok ? "Sent - check Telegram." : `Failed: ${result.reason ?? "unknown"}`}
              </span>
            )}
            {error && (
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
        )}
      </div>

      <div className={CARD}>
        <h3 className="text-xl font-semibold mb-3">What you can ask it</h3>
        <ul className="flex flex-col gap-2 text-sm text-muted-foreground">
          <li>
            <code className="text-foreground">/health</code> &mdash; the same check the terminal runs: whether the bot
            is up and toggled on, whether the turn is still advancing, its recent warnings, the display and the game
            window &mdash; <strong>with a screenshot of what is on screen</strong>, which is what tells you
            <em>why</em> a turn stopped advancing.
          </li>
          <li>
            <code className="text-foreground">/help</code> &mdash; the list of commands.
          </li>
        </ul>
        <p className="text-sm text-muted-foreground mt-4">
          Only the chat ID above is answered &mdash; anyone can find a bot by its name and message it, and nobody else
          gets to ask this machine anything.
        </p>
      </div>

      <div className={CARD}>
        <h3 className="text-xl font-semibold mb-3">What gets sent</h3>
        <ul className="flex flex-col gap-3 text-sm text-muted-foreground">
          <li>
            <span className="font-medium text-foreground">A career starts</span> &mdash; which number it is of the
            limit, the trainee, the borrowed card and the career's id, <strong>with the Final Confirmation
            screen</strong>: both Legacy parents and all six support cards, the borrowed Friends one included.
          </li>
          <li>
            <span className="font-medium text-foreground">A career finishes</span> &mdash; the final stats and the
            spark set that was kept, <strong>with the screen it finished on</strong>.
          </li>
          <li>
            <span className="font-medium text-foreground">The client freezes</span> &mdash; that it has stopped drawing
            and the game is being closed, with which restart attempt this is.
          </li>
          <li>
            <span className="font-medium text-foreground">The game comes back</span> &mdash; that it restarted and the
            career is resuming, or that the restart failed and the bot has stopped.
          </li>
        </ul>
        <p className="text-sm text-muted-foreground mt-4">
          Sending happens on its own thread, so an unreachable Telegram never holds the bot up, and a failure is a line
          in the log rather than an interrupted career.
        </p>
      </div>
    </div>
  );
}
