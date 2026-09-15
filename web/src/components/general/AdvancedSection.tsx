import { Cog } from "lucide-react";
import SleepMultiplier from "./SleepMultiplier";
import type { Config, UpdateConfigType } from "@/types";

type Props = {
  config: Config;
  updateConfig: UpdateConfigType;
};

export default function AdvancedSection({ config, updateConfig }: Props) {
  const { sleep_time_multiplier } = config;

  return (
    <div className="bg-card p-6 rounded-xl shadow-lg border border-border/20">
      <h2 className="text-3xl font-semibold mb-6 flex items-center gap-3">
        <Cog className="text-primary" />
        Advanced
      </h2>
      <SleepMultiplier
        sleepMultiplier={sleep_time_multiplier}
        setSleepMultiplier={(val) => updateConfig("sleep_time_multiplier", val)}
      />
    </div>
  );
}
