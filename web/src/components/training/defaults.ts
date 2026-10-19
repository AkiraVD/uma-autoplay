import type { Gamble } from "@/types";

// A preset saved before the "too good to pass" rule has no `gamble_board`
// block, so the Training tab falls back the way URA_FALLBACK does. These
// numbers must match config.template.json and core/state.py's own defaults.
export const GAMBLE_FALLBACK: Gamble = {
  enabled: true,
  ceiling_failure: 60,
  min_rainbows: 2,
  min_gain_points: 45,
  ev_margin: 1.25,
};
