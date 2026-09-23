import { ChevronsRight } from "lucide-react";
import PrioritizeG1 from "./PrioritizeG1";
import CancelConsecutive from "./CancelConsecutive";
import RaceSchedule from "./RaceSchedule";
import LoadRaceList from "./LoadRaceList";
import { Input } from "../ui/input";
import Tooltips from "../_c/Tooltips";
import type { Config, UpdateConfigType } from "@/types";

type Props = {
  config: Config;
  updateConfig: UpdateConfigType;
};

export default function RaceScheduleSection({ config, updateConfig }: Props) {
  const { prioritize_g1_race, cancel_consecutive_race, race_schedule } = config;
  // Presets saved before this existed don't have it.
  const maxRetries = config.max_race_retries ?? 1;

  return (
    <div className="bg-card p-6 rounded-xl shadow-lg border border-border/20">
      <h2 className="text-3xl font-semibold mb-6 flex items-center gap-3">
        <ChevronsRight className="text-primary" />
        Races
      </h2>
      <div className="flex flex-col gap-4">
        {/* The schedule picker sits right under the switch that turns it on. */}
        <PrioritizeG1
          prioritizeG1Race={prioritize_g1_race}
          setPrioritizeG1={(val) => updateConfig("prioritize_g1_race", val)}
        />
        <RaceSchedule
          raceSchedule={race_schedule}
          addRaceSchedule={(val) =>
            updateConfig("race_schedule", [...race_schedule, val])
          }
          deleteRaceSchedule={(name, year) =>
            updateConfig(
              "race_schedule",
              race_schedule.filter(
                (race) => race.name !== name || race.year !== year
              )
            )
          }
          clearRaceSchedule={() => updateConfig("race_schedule", [])}
        />
        {/* Built in the Race Plan tab, which never writes the config itself. */}
        <LoadRaceList onLoad={(rows) => updateConfig("race_schedule", rows)} />
        <CancelConsecutive
          cancelConsecutive={cancel_consecutive_race}
          setCancelConsecutive={(val) =>
            updateConfig("cancel_consecutive_race", val)
          }
        />
        <label className="flex flex-col gap-2">
          <span className="flex items-center gap-2 text-lg font-medium">
            Retries on a lost race
            <Tooltips>
              Each retry spends an Alarm Clock. A lost goal race ends the career,
              so 1 is worth it; 0 never retries.
            </Tooltips>
          </span>
          <Input className="w-24" type="number" min={0} max={5} value={maxRetries}
            onChange={(e) => updateConfig("max_race_retries", isNaN(e.target.valueAsNumber) ? 0 : e.target.valueAsNumber)} />
        </label>
      </div>
    </div>
  );
}
