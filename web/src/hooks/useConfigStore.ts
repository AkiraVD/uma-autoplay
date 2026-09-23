import { useCallback, useEffect, useState } from "react";
import { validateConfig } from "../utils/validateConfig";
import { URL } from "../constants";
import type { Config } from "../types";

export type SavedConfig = {
  name: string;
  config_name: string;
  trainee: string;
  scenario: string;
  // Both optional: a server older than the filters in the Saved configs dialog
  // doesn't send them, and neither does an unreadable preset.
  run_style?: string;
  distance?: string[];
  saved_at: number;
  unreadable?: boolean;
};

type Props = {
  config: Config;
  setConfig: (config: Config) => void;
  // useConfig's apply: it writes config.json and records what the server now
  // holds, so a load doesn't come back as one more unapplied change.
  apply: (config: Config) => Promise<boolean>;
};

// Fills keys an older preset lacks (a section added since it was saved) from
// the config on screen, so loading one doesn't fail validation. Carried over
// from the file-import path this replaced - presets on disk predate several
// sections, and without this they load as invalid rather than as themselves.
const deepMerge = <T extends object>(target: T, source: T): T => {
  const output = {} as T;

  for (const key in source) {
    if (
      source[key] &&
      typeof source[key] === "object" &&
      !Array.isArray(source[key])
    ) {
      output[key] = deepMerge(
        (target[key] as object) ?? {},
        source[key] as object
      ) as T[Extract<keyof T, string>];
    } else {
      output[key] = target[key] !== undefined ? target[key] : source[key];
    }
  }

  return output;
};

// "Maruzensky (Hot☆Summer Night) - Grand Concert Front/Long"
//   -> "maruzensky-hot-summer-night-grand-concert-front-long"
// The server sanitises the name again before it becomes a filename; this is
// only so the suggested name reads like the other presets in the folder.
export const slugify = (name: string) =>
  (name || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);

export function useConfigStore({ config, setConfig, apply }: Props) {
  const [saved, setSaved] = useState<SavedConfig[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${URL}/configs`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSaved(await res.json());
      setError(null);
    } catch (err) {
      setError(`Couldn't read the saved configs: ${(err as Error).message}`);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const detail = async (res: Response) => {
    try {
      return (await res.json())?.detail ?? `HTTP ${res.status}`;
    } catch {
      return `HTTP ${res.status}`;
    }
  };

  const save = async (name: string) => {
    const stem = slugify(name);
    if (!stem) {
      setError("Give the config a name before saving it.");
      return false;
    }
    setBusy(true);
    try {
      const res = await fetch(`${URL}/configs/${encodeURIComponent(stem)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      if (!res.ok) throw new Error(await detail(res));
      await refresh();
      setError(null);
      return true;
    } catch (err) {
      setError(`Save failed: ${(err as Error).message}`);
      return false;
    } finally {
      setBusy(false);
    }
  };

  // Loading puts the preset on screen AND applies it, matching what the file
  // import did - otherwise the page would show one config while the bot ran
  // another, which is the confusing half-state worth avoiding.
  const load = async (name: string) => {
    setBusy(true);
    try {
      const res = await fetch(`${URL}/configs/${encodeURIComponent(name)}`, {
        cache: "no-store",
      });
      if (!res.ok) throw new Error(await detail(res));
      const merged = deepMerge(await res.json(), config);

      const result = validateConfig(merged);
      if (!result.success) {
        setError(`'${name}' didn't validate: ${JSON.stringify(result.errors)}`);
        return false;
      }

      setConfig(merged);
      // At once rather than on the edit debounce: a load is one deliberate act,
      // and waiting would leave the page and the file apart for no reason.
      await apply(merged);
      setError(null);
      return true;
    } catch (err) {
      setError(`Load failed: ${(err as Error).message}`);
      return false;
    } finally {
      setBusy(false);
    }
  };

  const remove = async (name: string) => {
    setBusy(true);
    try {
      const res = await fetch(`${URL}/configs/${encodeURIComponent(name)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(await detail(res));
      await refresh();
      setError(null);
      return true;
    } catch (err) {
      setError(`Delete failed: ${(err as Error).message}`);
      return false;
    } finally {
      setBusy(false);
    }
  };

  return { saved, busy, error, setError, refresh, save, load, remove };
}
