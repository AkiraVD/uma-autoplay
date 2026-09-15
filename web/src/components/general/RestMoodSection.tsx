import { BatteryMedium } from "lucide-react";
import Mood from "./Mood";
import EnergySection from "../energy/EnergySection";
import type { Config, UpdateConfigType } from "@/types";

type Props = {
  config: Config;
  updateConfig: UpdateConfigType;
};

// When a turn rests, goes to the infirmary or skips training instead: the mood
// floors and the energy thresholds that decide it.
export default function RestMoodSection({ config, updateConfig }: Props) {
  const { minimum_mood, minimum_mood_junior_year } = config;

  return (
    <div className="bg-card p-6 rounded-xl shadow-lg border border-border/20">
      <h2 className="text-3xl font-semibold mb-6 flex items-center gap-3">
        <BatteryMedium className="text-primary" />
        Rest &amp; mood
      </h2>
      <div className="flex flex-col gap-6">
        <Mood
          minimumMood={minimum_mood}
          setMood={(val) => updateConfig("minimum_mood", val)}
          minimumMoodJunior={minimum_mood_junior_year}
          setMoodJunior={(val) => updateConfig("minimum_mood_junior_year", val)}
        />
        <EnergySection config={config} updateConfig={updateConfig} />
      </div>
    </div>
  );
}
