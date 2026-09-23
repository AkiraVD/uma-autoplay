import { EventSchema } from "./eventType";

import { z } from "zod";

export const StatSchema = z.object({
  spd: z.number(),
  sta: z.number(),
  pwr: z.number(),
  guts: z.number(),
  wit: z.number(),
});

export const SkillSchema = z.object({
  is_auto_buy_skill: z.boolean(),
  skill_pts_check: z.number(),
  skill_distance: z.array(z.string()),
  skill_run_style: z.string(),
});

export const RaceScheduleSchema = z.object({
  name: z.string(),
  year: z.string(),
  date: z.string(),
});

export const GrandConcertSchema = z.object({
  song_priority: z.array(z.string()),
  song_plan: z.array(z.number()),
  lyrics_option: z.number(),
  hold_for_top_songs: z.number(),
  energy_technique_below: z.number(),
  performance_short_points: z.number(),
  performance_urgent_points: z.number(),
  always_buy_gold_skill: z.boolean(),
});

// Starting the next career by itself, once one finishes. Optional so presets
// saved before it existed still parse.
export const CareerStartSchema = z.object({
  enabled: z.boolean(),
  borrow_card: z.string(),
  // 0 = no limit. Counts careers the bot starts itself, per bot run.
  max_consecutive: z.number().optional(),
});

export const ConfigSchema = z.object({
  config_name: z.string(),
  trainee: z.string(),
  // Presets saved before the Game mode setting don't have it; they mean "auto".
  // Trackblazer parked 2026-09-21; see core/parked/README.md.
  scenario: z.enum(["auto", "ura", "unity", "grand_concert"]).optional(),
  priority_stat: z.array(z.string()),
  priority_weights: z.array(z.number()),
  sleep_time_multiplier: z.number(),
  skip_training_energy: z.number(),
  never_rest_energy: z.number(),
  skip_infirmary_unless_missing_energy: z.number(),
  priority_weight: z.string(),
  minimum_mood: z.string(),
  minimum_mood_junior_year: z.string(),
  maximum_failure: z.number(),
  prioritize_g1_race: z.boolean(),
  cancel_consecutive_race: z.boolean(),
  max_race_retries: z.number(),
  reroll_sparks: z.boolean(),
  career_start: CareerStartSchema.optional(),
  position_selection_enabled: z.boolean(),
  enable_positions_by_race: z.boolean(),
  preferred_position: z.string(),
  positions_by_race: z.object({
    sprint: z.string(),
    mile: z.string(),
    medium: z.string(),
    long: z.string(),
  }),
  race_schedule: z.array(RaceScheduleSchema),
  stat_caps: StatSchema,
  skill: SkillSchema,
  event: EventSchema,
  grand_concert: GrandConcertSchema,
});

export type Stat = z.infer<typeof StatSchema>;
export type GrandConcert = z.infer<typeof GrandConcertSchema>;
export type Skill = z.infer<typeof SkillSchema>;
export type RaceScheduleType = z.infer<typeof RaceScheduleSchema>;
export type Config = z.infer<typeof ConfigSchema>;

export type UpdateConfigType = <K extends keyof Config>(
  key: K,
  value: Config[K]
) => void;
