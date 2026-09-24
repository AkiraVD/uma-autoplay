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
 * answers: `config` starts as the bundled template, and posting that would
 * quietly revert the real one. `applied` stays null until the server has been
 * read, and nothing is written while it is.
 *
 * Every write also quotes the version it read (X-Config-Version). A page left
 * open on an older config.json posts a whole document that would put every
 * setting changed since back the way it was - so the server refuses it, this
 * re-reads, and the person is told rather than left with a config that
 * silently reverted.
 */
export function useConfig(defaultConfig: Config) {
  const [config, setConfig] = useState<Config>(defaultConfig);
  const [applyState, setApplyState] = useState<ApplyState>("idle");
  const [applyError, setApplyError] = useState<string | null>(null);
  const applied = useRef<string | null>(null);
  const version = useRef<string | null>(null);

  // Reads config.json and takes it as the page's starting point, including the
  // version any later write has to quote.
  const read = useCallback(async () => {
    const res = await fetch(`${URL}/config`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    version.current = res.headers.get("X-Config-Version");
    applied.current = JSON.stringify(data);
    setConfig(data);
  }, []);

  const apply = useCallback(async (next: Config) => {
    const body = JSON.stringify(next);
    setApplyState("applying");
    try {
      const res = await fetch(`${URL}/config`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Config-Version": version.current ?? "",
        },
        body,
      });
      if (res.status === 409) {
        // Somebody else wrote the file since this page read it. Take theirs:
        // this page's copy is the older one, and posting it would undo their
        // change wholesale.
        const detail = await res.json().then((j) => j?.detail).catch(() => null);
        await read().catch(() => undefined);
        throw new Error(
          typeof detail === "string" ? detail : "CFG-E10 the config changed elsewhere."
        );
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      version.current = res.headers.get("X-Config-Version") ?? version.current;
      applied.current = body;
      setApplyState("applied");
      setApplyError(null);
      return true;
    } catch (err) {
      setApplyState("error");
      setApplyError((err as Error).message);
      return false;
    }
  }, [read]);

  useEffect(() => {
    read().catch((err: Error) => {
      setApplyState("error");
      setApplyError(
        `Couldn't read the config (${err.message}); edits on this page are not being applied.`
      );
    });
  }, [read]);

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
