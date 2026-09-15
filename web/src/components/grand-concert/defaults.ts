import type { GrandConcert } from "@/types";

// A preset saved before the Grand Concert settings existed has no grand_concert
// block. Shared by every section that reads or writes one of its fields: the
// gold skill checkbox lives in the Skills section, the rest in Grand Concert.
export const GRAND_CONCERT_FALLBACK: GrandConcert = {
  song_priority: [],
  song_plan: [4, 8, 12, 16, 18],
  lyrics_option: 5,
  hold_for_top_songs: 2,
  energy_technique_below: 50,
  performance_short_points: 0.75,
  performance_urgent_points: 4.0,
  always_buy_gold_skill: false,
};
