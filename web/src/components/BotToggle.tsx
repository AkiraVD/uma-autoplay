import { useCallback, useEffect, useState } from "react";
import { Loader2, Play, Square } from "lucide-react";

import { URL } from "@/constants";
import { Button } from "./ui/button";

// What /bot/status returns; see server/main.py. "stopping" is a stopped bot
// whose thread has not finished its current step yet.
type BotState = "running" | "stopped" | "stopping";

const POLL_MS = 2000;

export default function BotToggle() {
  const [botState, setBotState] = useState<BotState | null>(null);
  const [busy, setBusy] = useState(false);
  // Every failure carries a code: plain words get read as a diagnosis.
  const [fault, setFault] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${URL}/bot/status`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setBotState((await res.json()).state);
      setFault(null);
    } catch {
      setBotState(null);
      setFault("BOT-E10 can't reach /bot/status - is main.py running?");
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  const send = async (action: "start" | "stop") => {
    // The page is reachable from other devices, so a stray tap must not set the
    // bot clicking. Stopping needs no confirmation.
    if (action === "start" && !window.confirm("Start the bot? It will begin playing the game.")) return;
    setBusy(true);
    try {
      const res = await fetch(`${URL}/bot/${action}`, { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().then((j) => j?.detail).catch(() => null);
        throw new Error(typeof detail === "string" ? detail : `HTTP ${res.status}`);
      }
      setBotState((await res.json()).state);
      setFault(null);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setFault(message.startsWith("BOT-") ? message : `BOT-E11 couldn't ${action} the bot (${message})`);
    } finally {
      setBusy(false);
    }
  };

  const running = botState === "running";
  const Icon = busy || botState === "stopping" ? Loader2 : running ? Square : Play;
  const label = botState === null ? "Bot offline" : botState === "stopping" ? "Stopping..." : running ? "Stop bot" : "Start bot";

  return (
    <Button
      size="sm"
      variant={running ? "destructive" : "default"}
      disabled={busy || botState === null || botState === "stopping"}
      title={fault ?? (running ? "Stop the bot (same as Pause)" : "Start the bot (same as Pause)")}
      onClick={() => send(running ? "stop" : "start")}
    >
      <Icon className={`size-4 ${Icon === Loader2 ? "animate-spin" : ""}`} />
      {label}
    </Button>
  );
}
