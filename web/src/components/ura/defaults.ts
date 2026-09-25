import type { Ura } from "@/types";

// A preset saved before the URA settings existed has no `ura` block, and the
// duel settings are read from two different cards, so the fallback is shared
// the way GRAND_CONCERT_FALLBACK is.
export const URA_FALLBACK: Ura = {
  chase_duels: true,
  duel_targets: ["energy", "sta"],
  force_buy_skills: ["Racing Spirit: Mood"],
  keep_sparks: ["Racing Spirit: Mood", "Racing Spirit: Stamina"],
};
