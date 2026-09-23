import { useCallback, useEffect, useState } from "react";
import { Send, MessageCircle, Save } from "lucide-react";
import { Button } from "../ui/button";
import { Checkbox } from "../ui/checkbox";
import { Input } from "../ui/input";
import { URL } from "@/constants";

type Settings = { enabled: boolean; token: string; chat_id: string };

const EMPTY: Settings = { enabled: false, token: "", chat_id: "" };
const CARD = "bg-card p-6 rounded-xl shadow-lg border border-border/20";

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
// telegram.json is gitignored so the token stays on this machine. The page
// shows Save, Saved and what was sent - the rest is this comment's business.
export default function TelegramView() {
  const [settings, setSettings] = useState<Settings>(EMPTY);
  const [loaded, setLoaded] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ ok: boolean; reason?: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${URL}/telegram`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSettings({ ...EMPTY, ...(await res.json()) });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "could not reach the server");
    } finally {
      setLoaded(true);
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const set = (patch: Partial<Settings>) => {
    setSettings((s) => ({ ...s, ...patch }));
    setDirty(true);
    setSaved(false);
  };

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${URL}/telegram`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSettings({ ...EMPTY, ...(await res.json()) });
      setDirty(false);
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "could not save");
    } finally {
      setBusy(false);
    }
  };

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
            <Button className="font-semibold" onClick={save} disabled={busy || !dirty}>
              <Save className="size-4" />
              {busy ? "Saving..." : dirty ? "Save" : "Saved"}
            </Button>
            <Button variant="outline" onClick={test}
              disabled={busy || !settings.token || !settings.chat_id}>
              <Send className="size-4" />
              Send a test message
            </Button>
            {saved && !dirty && (
              <span className="text-green-600 dark:text-green-400">Saved - the bot is using it now.</span>
            )}
            {result && (
              <span className={result.ok ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}>
                {result.ok ? "Sent - check Telegram." : `Failed: ${result.reason ?? "unknown"}`}
              </span>
            )}
            {error && <span className="text-red-600 dark:text-red-400">{error}</span>}
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
            window.
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
            limit, the trainee, the borrowed card and the career's id.
          </li>
          <li>
            <span className="font-medium text-foreground">A career finishes</span> &mdash; the final stats and the
            spark set that was kept.
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
