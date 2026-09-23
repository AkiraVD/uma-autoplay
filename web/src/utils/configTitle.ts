import type { Config } from "@/types";
import { capitalise, DISTANCES } from "./aptitudes";
import { scenarioLabel, type Scenario } from "./scenarios";

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

/** The four fields a title is made of, from wherever they are held. */
type Source = {
  trainee?: string;
  scenario?: string;
  runStyle?: string;
  distance?: string[];
};

/** The parts, so the toolbar can set them apart without re-splitting a string. */
export const partsFrom = ({ trainee, scenario, runStyle, distance }: Source) => ({
  // The trainee's name as master.mdb gives it, epithet and all (core/trainee.py
  // matches on category 4): two cards of the same character train differently,
  // so the epithet is part of what the config is.
  trainee: (trainee || "").trim(),
  // Auto-detect names no scenario - the screen decides it - so there is nothing
  // to put in the title until the mode is actually chosen. A key the picker no
  // longer offers (a preset saved under Trackblazer, parked 2026-09-21) is shown
  // as it was written rather than dropped, since the file really does say it.
  scenario:
    !scenario || scenario === "auto"
      ? ""
      : scenarioLabel(scenario as Scenario) || capitalise(scenario),
  // Distances is a set: an Uma with two aptitudes races both. Sorted shortest
  // first, as the buttons are laid out - otherwise the title reads back the
  // order they happened to be clicked in.
  runs: [
    runStyle ?? "",
    ...[...(distance ?? [])].sort((a, b) => DISTANCES.indexOf(a) - DISTANCES.indexOf(b)),
  ]
    .filter(Boolean)
    .map(capitalise)
    .join("/"),
});

export const joinTitle = (parts: ReturnType<typeof partsFrom>) =>
  [parts.trainee, parts.scenario, parts.runs].filter(Boolean).join(" - ");

export const titleParts = (config: Config) =>
  partsFrom({
    trainee: config.trainee,
    scenario: config.scenario,
    runStyle: config.skill.skill_run_style,
    distance: config.skill.skill_distance,
  });

export const configTitle = (config: Config) => joinTitle(titleParts(config)) || "No trainee";
