import { useCallback, useEffect, useRef, useState } from "react";
import { URL } from "../constants";
import type { Config } from "../types";

export type ApplyState = "idle" | "applying" | "applied" | "error";

// Long enough that typing a number doesn't write the file per keystroke, short
// enough that nobody leaves the page before their last edit lands.
const DEBOUNCE = 500;

/**
 * The config on screen, kept the same as the config on disk.
 *
 * There used to be an Apply button, and a page that had been edited but not
 * applied looked exactly like one that had - so the bot would start on the
 * settings from an hour ago. Every change is written now, debounced, and the
 * toolbar says when it landed.
 *
 * POST /config only writes config.json; core/state.py::reload_config() reads it
 * when the bot *starts*. So "applied" means the next career uses it, and a
 * career already running is not disturbed mid-turn.
 *
 * The one thing auto-applying must never do is write before the first GET
 * answers: `config` starts as the config.json that was bundled at build time,
 * and posting that would quietly revert the real one. `applied` stays null
 * until the server has been read, and nothing is written while it is.
 */
export function useConfig(defaultConfig: Config) {
  const [config, setConfig] = useState<Config>(defaultConfig);
  const [applyState, setApplyState] = useState<ApplyState>("idle");
  const [applyError, setApplyError] = useState<string | null>(null);
  const applied = useRef<string | null>(null);

  const apply = useCallback(async (next: Config) => {
    const body = JSON.stringify(next);
    setApplyState("applying");
    try {
      const res = await fetch(`${URL}/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      applied.current = body;
      setApplyState("applied");
      setApplyError(null);
      return true;
    } catch (err) {
      setApplyState("error");
      setApplyError((err as Error).message);
      return false;
    }
  }, []);

  useEffect(() => {
    const getConfig = async () => {
      try {
        const res = await fetch(`${URL}/config`, { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        applied.current = JSON.stringify(data);
        setConfig(data);
      } catch (err) {
        setApplyState("error");
        setApplyError(
          `Couldn't read the config (${(err as Error).message}); edits on this page are not being applied.`
        );
      }
    };
    getConfig();
  }, []);

  useEffect(() => {
    if (applied.current === null) return;
    if (JSON.stringify(config) === applied.current) return;
    // Said as soon as the page differs from the file, not when the write goes
    // out, so the indicator never reads "Applied" over an unapplied edit.
    setApplyState("applying");
    const timer = setTimeout(() => void apply(config), DEBOUNCE);
    return () => clearTimeout(timer);
  }, [config, apply]);

  return { config, setConfig, apply, applyState, applyError };
}
