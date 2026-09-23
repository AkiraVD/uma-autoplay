import { useState } from "react";
import { Send, MessageCircle } from "lucide-react";
import { Button } from "../ui/button";
import { Checkbox } from "../ui/checkbox";
import { Input } from "../ui/input";
import { URL } from "@/constants";
import type { Config, UpdateConfigType } from "@/types";

type Props = {
  config: Config;
  updateConfig: UpdateConfigType;
};

const FALLBACK = { enabled: false, token: "", chat_id: "" };
const CARD = "bg-card p-6 rounded-xl shadow-lg border border-border/20";

// Telegram, for following a run nobody is watching. Its own tab because the
// token is a secret and does not belong beside the training weights, and
// because the setup is a one-off that wants room to explain itself.
export default function TelegramView({ config, updateConfig }: Props) {
  const telegram = { ...FALLBACK, ...(config.telegram ?? {}) };
  const set = (patch: Partial<typeof FALLBACK>) =>
    updateConfig("telegram", { ...telegram, ...patch });

  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; reason?: string } | null>(null);
  // The test posts what is typed rather than what is saved, so it works before
  // Apply - which is exactly when the details are most likely to be wrong.
  const test = async () => {
    setBusy(true);
    setResult(null);
    try {
      const res = await fetch(`${URL}/telegram/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: telegram.token, chat_id: telegram.chat_id }),
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
        <div className="flex flex-col gap-6">
          <div className="w-fit">
            <label htmlFor="telegram-enabled" className="flex gap-2 items-start">
              <Checkbox id="telegram-enabled" className="mt-1.5" checked={telegram.enabled}
                onCheckedChange={() => set({ enabled: !telegram.enabled })} />
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
              value={telegram.token}
              onChange={(e) => set({ token: e.target.value })} />
            <span className="block text-sm text-muted-foreground mt-1">
              From <strong>@BotFather</strong> in Telegram: send it <code>/newbot</code>, pick a name, and it replies
              with the token. This is a secret &mdash; it is stored in <code>config.json</code> and in any preset you
              save, both of which stay on this machine.
            </span>
          </div>

          <div>
            <label htmlFor="telegram-chat" className="block text-lg font-medium">
              Chat ID
            </label>
            <Input id="telegram-chat" className="w-64 mt-1 font-mono"
              placeholder="123456789"
              value={telegram.chat_id}
              onChange={(e) => set({ chat_id: e.target.value })} />
            <span className="block text-sm text-muted-foreground mt-1">
              Your own chat with the bot, not the bot's name. Message your new bot once, then open
              <code className="mx-1">api.telegram.org/bot&lt;token&gt;/getUpdates</code> in a browser and read
              <code className="mx-1">result[0].message.chat.id</code>. A group works too; its id starts with
              <code className="mx-1">-</code>.
            </span>
          </div>

          <div className="flex items-center gap-3">
            <Button onClick={test} disabled={busy || !telegram.token || !telegram.chat_id}>
              <Send className="size-4" />
              {busy ? "Sending..." : "Send a test message"}
            </Button>
            {result && (
              <span className={result.ok ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}>
                {result.ok ? "Sent - check Telegram." : `Failed: ${result.reason ?? "unknown"}`}
              </span>
            )}
          </div>
          <span className="text-sm text-muted-foreground -mt-2">
            The test uses what is typed above, so it works before Apply. Everything else needs Apply to take effect.
          </span>
        </div>
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
