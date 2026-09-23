// The two aptitude vocabularies, shared because they are also how saved
// configs are filtered. Order matters: it is the order the pickers lay the
// buttons out in, shortest distance first, and core.skill_score.RUNNING_STYLES
// front to back.
export const DISTANCES = ["sprint", "mile", "medium", "long"];
export const RUN_STYLES = ["front", "pace", "late", "end"];

export const capitalise = (word: string) =>
  word ? word[0].toUpperCase() + word.slice(1) : word;
