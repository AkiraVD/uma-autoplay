import type { Config } from "@/types";

export type Scenario = NonNullable<Config["scenario"]>;

// Mirrors core/state.py SCENARIOS, in the order the picker lists them.
// Trackblazer was parked on 2026-09-21 and removed from both; a config still
// holding it falls back to Auto-detect with a warning (core/state.py
// resolve_scenario). See core/parked/README.md.
export const SCENARIOS: [Scenario, string][] = [
  ["auto", "Auto-detect"],
  ["ura", "URA Finale"],
  ["unity", "Unity Cup"],
  ["grand_concert", "Grand Concert"],
];

export const scenarioLabel = (scenario: Scenario) =>
  SCENARIOS.find(([key]) => key === scenario)?.[1] ?? "";
