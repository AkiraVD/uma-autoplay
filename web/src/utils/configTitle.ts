import type { Config } from "@/types";

/**
 * The name the config goes by, built from the config itself.
 *
 * It used to be free text, and free text goes stale: the toolbar read
 * "Maruzensky (Hot☆Summer Night) - Grand Concert Front/Mile" while the trainee
 * picker below it held Mihono Bourbon, because nothing made anyone retype it.
 * Deriving it costs the custom label and keeps the three things that actually
 * decide a config - who runs, how she runs, how far - honest.
 *
 * A preset can still be filed under any name: the Save dialog takes one, and
 * only offers this as the default.
 */

// Trainee names come from master.mdb as "[Epithet] Name" (core/trainee.py,
// category 4). The epithet says which card; the name says who, which is what a
// title is for.
export const traineeName = (trainee: string) =>
  (trainee || "").replace(/^\s*\[[^\]]*\]\s*/, "").trim();

const capitalise = (word: string) =>
  word ? word[0].toUpperCase() + word.slice(1) : word;

// Shortest first, as the buttons are laid out. Without this the title would
// read back the order the distances happened to be clicked in.
const DISTANCES = ["sprint", "mile", "medium", "long"];

export const configTitle = (config: Config) => {
  const who = traineeName(config.trainee);
  // Distances is a set - an Uma with two aptitudes races both - so all of them
  // go in.
  const distances = [...config.skill.skill_distance].sort(
    (a, b) => DISTANCES.indexOf(a) - DISTANCES.indexOf(b)
  );
  const runs = [config.skill.skill_run_style, ...distances]
    .filter(Boolean)
    .map(capitalise)
    .join("/");
  if (!who) return runs || "No trainee";
  return runs ? `${who} - ${runs}` : who;
};
