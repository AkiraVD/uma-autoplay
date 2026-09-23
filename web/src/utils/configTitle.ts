import type { Config } from "@/types";
import { capitalise, DISTANCES } from "./aptitudes";
import { scenarioLabel } from "./scenarios";

/**
 * The name the config goes by, built from the config itself.
 *
 * It used to be free text, and free text goes stale: the toolbar read
 * "Maruzensky (Hot☆Summer Night) - Grand Concert Front/Mile" while the trainee
 * picker below it held Mihono Bourbon, because nothing made anyone retype it.
 * Deriving it costs the custom label and keeps the four things that decide a
 * config - who runs, in which scenario, how she runs and how far - honest.
 *
 * A preset can still be filed under any name: the Save dialog takes one, and
 * only offers this as the default.
 *
 *   [CODE: ICING] Mihono Bourbon - Grand Concert - Front/Long
 */

// Sorted shortest first, as the buttons are laid out: without this the title
// would read back the order the distances happened to be clicked in.

/** The parts, so the toolbar can set them apart without re-splitting a string. */
export const titleParts = (config: Config) => {
  // The trainee's name as master.mdb gives it, epithet and all (core/trainee.py
  // matches on category 4): two cards of the same character train differently,
  // so the epithet is part of what the config is.
  const trainee = (config.trainee || "").trim();
  // Auto-detect names no scenario - the screen decides it - so there is nothing
  // to put in the title until the mode is actually chosen.
  const scenario = config.scenario && config.scenario !== "auto"
    ? scenarioLabel(config.scenario)
    : "";
  // Distances is a set: an Uma with two aptitudes races both.
  const distances = [...config.skill.skill_distance].sort(
    (a, b) => DISTANCES.indexOf(a) - DISTANCES.indexOf(b)
  );
  const runs = [config.skill.skill_run_style, ...distances]
    .filter(Boolean)
    .map(capitalise)
    .join("/");
  return { trainee, scenario, runs };
};

export const configTitle = (config: Config) => {
  const { trainee, scenario, runs } = titleParts(config);
  const named = [trainee, scenario, runs].filter(Boolean).join(" - ");
  return named || "No trainee";
};
